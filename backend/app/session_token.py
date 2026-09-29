"""세션 토큰 — "내가 이 사람이다"를 증명하는 최소 장치.

지금까지는 X-User-Id 헤더 하나로 신원을 주장할 수 있었다. 사용자 id 는 공유
링크나 코스 소유자 정보로 새어 나갈 수 있는 값이라, id 만 알면 남의 크레딧을
쓰고 계정을 지울 수 있었다.

가입·인증 시 발급한 서명 토큰을 함께 보내게 한다. 비밀키가 없는 개발 환경에서는
종전대로 헤더를 믿되(로컬 편의), 배포에서는 SESSION_SECRET 을 반드시 설정한다.

토큰은 **발급 시각을 포함**해 90일 뒤 만료된다. 만료가 없으면 한 번 새어 나간
토큰이 영원히 유효하고, 기기를 잃어버려도 되돌릴 방법이 없다. 만료된 토큰으로
온 요청은 401 이고, 프론트는 그때 재인증 화면으로 보낸다.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time

from app.config import settings

logger = logging.getLogger("coursepilot")
_warned = False

MAX_AGE_SEC = 90 * 24 * 60 * 60  # 90일
_SEP = "."


def enabled() -> bool:
    """비밀키가 설정된 환경에서만 토큰을 강제한다."""
    if settings.session_secret:
        return True
    global _warned
    if not _warned:
        _warned = True
        logger.warning(
            "SESSION_SECRET 미설정 — 사용자 id 헤더만으로 인증됩니다(개발용). 배포 전 설정하세요."
        )
    return False


def _sign(payload: str) -> str:
    mac = hmac.new(
        settings.session_secret.encode(), payload.encode(), hashlib.sha256
    ).digest()
    return base64.urlsafe_b64encode(mac).decode().rstrip("=")


def issue(user_id: str, issued_at: int | None = None) -> str:
    """`<발급시각>.<서명>` 형태의 토큰. 비밀키가 없으면 빈 문자열.

    서명 대상은 `user_id:issued_at` 이라 발급 시각을 위조할 수 없다.
    """
    if not settings.session_secret:
        return ""
    stamp = int(issued_at if issued_at is not None else time.time())
    return f"{stamp}{_SEP}{_sign(f'{user_id}:{stamp}')}"


def expired(token: str | None, *, now: int | None = None) -> bool:
    """서명과 무관하게 발급 시각만 보고 만료 여부를 본다."""
    stamp, _, _sig = (token or "").partition(_SEP)
    if not stamp.isdigit():
        return True
    age = int(now if now is not None else time.time()) - int(stamp)
    return age < 0 or age > MAX_AGE_SEC


def verify(user_id: str, token: str | None, *, now: int | None = None) -> bool:
    """토큰이 그 사용자의 것이고 아직 만료되지 않았는지.

    비밀키가 없으면(개발) 검사하지 않는다.
    """
    if not enabled():
        return True
    if not token:
        return False
    stamp, sep, _sig = token.partition(_SEP)
    if not sep or not stamp.isdigit():
        return False  # 만료 없는 구형 토큰은 더 이상 받지 않는다(재인증 유도)
    if expired(token, now=now):
        return False
    return hmac.compare_digest(issue(user_id, int(stamp)), token)
