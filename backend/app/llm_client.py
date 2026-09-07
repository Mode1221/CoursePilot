"""OpenAI 클라이언트 싱글턴 (키 검사 + 재사용). 연결 풀 재사용으로 요청당 생성 방지."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.config import settings


@lru_cache(maxsize=1)
def get_openai_client() -> Any | None:
    """키가 있으면 캐시된 AsyncOpenAI, 없으면 None."""
    if not settings.openai_api_key:
        return None
    from openai import AsyncOpenAI

    return AsyncOpenAI(api_key=settings.openai_api_key)
