"""세션 토큰 — "내가 이 사람이다"를 증명하는 최소 장치.

지금까지는 X-User-Id 헤더 하나로 신원을 주장할 수 있었다. 사용자 id 는 공유
링크나 코스 소유자 정보로 새어 나갈 수 있는 값이라, id 만 알면 남의 크레딧을
쓰고 계정을 지울 수 있었다.

가입·인증 시 발급한 서명 토큰을 함께 보내게 한다. 비밀키가 없는 개발 환경에서는
종전대로 헤더를 믿되(로컬 편의), 배포에서는 SESSION_SECRET 을 반드시 설정한다.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging

from app.config import settings

logger = logging.getLogger("coursepilot")
_warned = False


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


def issue(user_id: str) -> str:
    """사용자 id 에 대한 서명 토큰. 비밀키가 없으면 빈 문자열."""
    if not settings.session_secret:
        return ""
    mac = hmac.new(
        settings.session_secret.encode(), user_id.encode(), hashlib.sha256
    ).digest()
    return base64.urlsafe_b64encode(mac).decode().rstrip("=")


def verify(user_id: str, token: str | None) -> bool:
    """토큰이 그 사용자의 것인지. 비밀키가 없으면 검사하지 않는다."""
    if not enabled():
        return True
    if not token:
        return False
    return hmac.compare_digest(issue(user_id), token)
