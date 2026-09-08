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


class VerificationStore:
    def __init__(self) -> None:
        self._codes: dict[str, tuple[str, float]] = {}      # phone -> (code, expiry)
        self._verified: dict[str, float] = {}                # phone -> expiry

    def issue(self, phone: str) -> str:
        code = f"{secrets.randbelow(1_000_000):06d}"
        self._codes[phone] = (code, _time.time() + _CODE_TTL)
        return code

    def verify(self, phone: str, code: str) -> bool:
        entry = self._codes.get(phone)
        if not entry or entry[1] < _time.time() or entry[0] != code:
            return False
        del self._codes[phone]
        self._verified[phone] = _time.time() + _VERIFIED_TTL
        return True

    def is_verified(self, phone: str) -> bool:
        exp = self._verified.get(phone)
        return exp is not None and exp >= _time.time()

    def consume_verified(self, phone: str) -> None:
        self._verified.pop(phone, None)


verification_store = VerificationStore()


async def request_code(phone: str) -> str | None:
    """코드 발급 + 발송. 실서비스면 None(코드 비노출), 개발 폴백이면 코드 반환."""
    code = verification_store.issue(phone)
    from app.adapters.sms import get_sms_service

    sms = get_sms_service()
    if sms is None:
        return code  # 개발용: 발송 없이 코드 노출
    await sms.send(phone, f"[CoursePilot] 인증번호 {code}")
    return None


def require_verified(phone: str) -> bool:
    """가입 진행 가능 여부. SMS 비활성(개발)이면 항상 통과."""
    if not settings.sms_enabled:
        return True
    return verification_store.is_verified(phone)
