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


async def request_code(phone: str) -> str | None:
    """코드 발급 + 발송. 실서비스면 None(코드 비노출), 개발 폴백이면 코드 반환.

    같은 번호로 짧은 간격·과도한 횟수 요청은 거절한다(TooManyRequests).
    """
    if not verification_store.can_send(phone):
        raise TooManyRequests
    code = verification_store.issue(phone)
    from app.adapters.sms import get_sms_service
    from app.metrics import metrics_store

    sms = get_sms_service()
    if sms is None:
        return code  # 개발용: 발송 없이 코드 노출
    try:
        sent = await sms.send(phone, f"[CoursePilot] 인증번호 {code}")
    except Exception as exc:  # 벤더 오류를 500 이 아니라 명확한 실패로 알린다
        metrics_store.record_external("sms.send", ok=False)
        raise SmsSendFailed from exc
    metrics_store.record_external("sms.send", ok=bool(sent))
    if not sent:
        raise SmsSendFailed
    return None


def require_verified(phone: str) -> bool:
    """가입 진행 가능 여부. SMS 비활성(개발)이면 항상 통과."""
    if not settings.sms_enabled:
        return True
    return verification_store.is_verified(phone)
