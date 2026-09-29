"""전화번호 SMS 인증 (9장 가입).

- 6자리 코드 발급 → SMS 발송(키 있으면 NHN Cloud, 없으면 개발용으로 코드 반환).
- 코드 검증 성공 시 해당 번호를 '인증됨'으로 표시 → signup 허용.
- 인메모리 저장(코드 TTL 5분, 인증 상태 30분). 분산 배포 시 Redis 등으로 교체.
"""
from __future__ import annotations

import secrets
import time as _time

from app.config import settings

_CODE_TTL = 300      # 코드 유효 5분
_VERIFIED_TTL = 1800  # 인증 상태 유지 30분
MAX_ATTEMPTS = 5     # 코드 시도 횟수 상한(6자리 무차별 대입 차단)
RESEND_COOLDOWN = 60   # 같은 번호로 재발송 최소 간격(초)
MAX_SENDS_PER_HOUR = 5  # 번호당 시간당 발송 상한(문자 폭탄·비용 방지)
# 한 IP 가 번호를 바꿔 가며 보내면 번호당 상한을 비켜 간다(문자 비용 공격). IP 당 하루 상한.
MAX_SENDS_PER_IP_DAY = 10


def normalize_phone(phone: str) -> str:
    """전화번호를 숫자만 남긴 한 가지 표기로 맞춘다.

    "010-1234-5678", "01012345678", "+82 10-1234-5678" 이 각각 다른 계정이 되면
    사용자는 지난 코스·크레딧을 잃고, 번호별 발송 제한도 우회된다.
    """
    digits = "".join(ch for ch in phone if ch.isdigit())
    if digits.startswith("82") and len(digits) >= 11:
        digits = "0" + digits[2:]
    return digits


class TooManyRequests(Exception):
    """발송 쿨다운/상한 초과."""


class SmsSendFailed(Exception):
    """SMS 발송 실패(벤더 오류)."""


class VerificationStore:
    def __init__(self) -> None:
        self._codes: dict[str, tuple[str, float]] = {}      # phone -> (code, expiry)
        self._verified: dict[str, float] = {}                # phone -> expiry
        self._attempts: dict[str, int] = {}                  # phone -> 남은 시도 수
        self._sends: dict[str, list[float]] = {}             # phone -> 최근 발송 시각들
        self._ip_sends: dict[str, list[float]] = {}          # ip -> 최근 발송 시각들(하루)

    def can_send_from(self, ip: str) -> bool:
        """IP 당 하루 발송 상한. 통과하면 기록한다(빈 IP 는 검사하지 않는다 — 테스트·내부 호출)."""
        if not ip:
            return True
        now = _time.time()
        recent = [t for t in self._ip_sends.get(ip, []) if now - t < 86400]
        if len(recent) >= MAX_SENDS_PER_IP_DAY:
            self._ip_sends[ip] = recent
            return False
        recent.append(now)
        self._ip_sends[ip] = recent
        return True

    def can_send(self, phone: str) -> bool:
        """쿨다운·시간당 상한 확인. 통과하면 발송 이력을 기록한다."""
        now = _time.time()
        recent = [t for t in self._sends.get(phone, []) if now - t < 3600]
        if recent and now - recent[-1] < RESEND_COOLDOWN:
            return False
        if len(recent) >= MAX_SENDS_PER_HOUR:
            self._sends[phone] = recent
            return False
        recent.append(now)
        self._sends[phone] = recent
        return True

    def issue(self, phone: str) -> str:
        self._sweep()
        code = f"{secrets.randbelow(1_000_000):06d}"
        self._codes[phone] = (code, _time.time() + _CODE_TTL)
        self._attempts[phone] = MAX_ATTEMPTS  # 재발급하면 시도 횟수도 초기화
        return code

    def verify(self, phone: str, code: str) -> bool:
        entry = self._codes.get(phone)
        if not entry or entry[1] < _time.time():
            self._forget(phone)
            return False
        if entry[0] != code:
            # 틀린 시도가 쌓이면 코드를 폐기한다(무차별 대입 차단, 재발급 필요)
            self._attempts[phone] = self._attempts.get(phone, MAX_ATTEMPTS) - 1
            if self._attempts[phone] <= 0:
                self._forget(phone)
            return False
        self._forget(phone)
        self._verified[phone] = _time.time() + _VERIFIED_TTL
        return True

    def _forget(self, phone: str) -> None:
        self._codes.pop(phone, None)
        self._attempts.pop(phone, None)

    def _sweep(self) -> None:
        """만료된 코드·인증 상태 정리(무한 증가 방지)."""
        now = _time.time()
        for phone in [p for p, (_, exp) in self._codes.items() if exp < now]:
            self._forget(phone)
        for phone in [p for p, exp in self._verified.items() if exp < now]:
            del self._verified[phone]
        for phone in [p for p, ts in self._sends.items() if not ts or now - ts[-1] >= 3600]:
            del self._sends[phone]

    def is_verified(self, phone: str) -> bool:
        exp = self._verified.get(phone)
        return exp is not None and exp >= _time.time()

    def consume_verified(self, phone: str) -> None:
        self._verified.pop(phone, None)


verification_store = VerificationStore()


async def request_code(phone: str, ip: str = "") -> str | None:
    """코드 발급 + 발송. 실서비스면 None(코드 비노출), 개발 폴백이면 코드 반환.

    같은 번호로 짧은 간격·과도한 횟수 요청은 거절한다(TooManyRequests).
    """
    if not verification_store.can_send(phone) or not verification_store.can_send_from(ip):
        raise TooManyRequests
    code = verification_store.issue(phone)
    from app.adapters.sms import get_sms_service
    from app.metrics import metrics_store

    sms = get_sms_service()
    if sms is None:
        return code  # 개발용: 발송 없이 코드 노출
    try:
        sent = await sms.send(phone, f"[픽앤어스] 인증번호 {code}")
    except Exception as exc:  # 벤더 오류를 500 이 아니라 명확한 실패로 알린다
        metrics_store.record_external("sms.send", ok=False)
        raise SmsSendFailed from exc
    metrics_store.record_external("sms.send", ok=bool(sent))
    if not sent:
        raise SmsSendFailed
    return None


def require_verified(phone: str) -> bool:
    """가입 진행 가능 여부.

    - SMS 가 켜져 있으면 인증번호를 맞힌 번호만.
    - 운영에서 SMS 가 꺼져 있으면: 개발 폴백(SMS_DEV_FALLBACK)일 때만 인증번호 확인을 거치고,
      그것도 아니면 **거절**. 예전에는 무조건 통과라 전화번호만 알면 남의 계정 토큰을 받았다.
    - 개발(로컬·테스트)에서 SMS 가 없으면 통과(편의).
    """
    if settings.sms_enabled or (settings.is_production and settings.sms_dev_fallback):
        return verification_store.is_verified(phone)
    return not settings.is_production


def can_resume_existing() -> bool:
    """인증만으로 **이미 있는 계정**에 다시 들어갈 수 있는가.

    개발 폴백은 인증번호를 화면에 그대로 보여 준다 — 남의 번호로도 번호를 받아 맞힐 수 있다.
    그 상태에서 기존 계정 토큰을 내주면 곧 계정 탈취다. 운영에서는 진짜 SMS 일 때만 허용한다.
    """
    return settings.sms_enabled or not settings.is_production
