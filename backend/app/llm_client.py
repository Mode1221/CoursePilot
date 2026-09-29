"""OpenAI 클라이언트 싱글턴 (키 검사 + 재사용). 연결 풀 재사용으로 요청당 생성 방지."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.config import settings

# SDK 기본 타임아웃은 10분이다. 코스 큐가 그만큼 잠기면 사용자는 화면이 멈춘 것으로 본다.
# 조건 분해는 짧은 호출이라 20초면 충분하고, 넘으면 규칙 기반 폴백이 낫다.
LLM_TIMEOUT_SEC = 20.0
LLM_MAX_RETRIES = 1


def _within_daily_budget() -> bool:
    """서비스 전체 LLM 하루 상한. 넘으면 None 을 돌려 호출부가 규칙 기반으로 폴백한다.

    호출부마다 상한을 넣는 대신 여기 한 곳에서 막는다 — 새 LLM 기능이 생겨도 빠지지 않게.
    """
    from app.usage import global_take

    return global_take("llm")


def get_openai_client() -> Any | None:
    """키가 있고 오늘 LLM 몫이 남았으면 캐시된 AsyncOpenAI, 아니면 None."""
    client = _openai_client()
    if client is None or not _within_daily_budget():
        return None
    return client


def get_anthropic_client() -> Any | None:
    """키가 있고 오늘 LLM 몫이 남았으면 캐시된 AsyncAnthropic, 아니면 None."""
    client = _anthropic_client()
    if client is None or not _within_daily_budget():
        return None
    return client


@lru_cache(maxsize=1)
def _openai_client() -> Any | None:
    """키가 있으면 캐시된 AsyncOpenAI, 없으면 None."""
    if not settings.openai_api_key:
        return None
    from openai import AsyncOpenAI

    return AsyncOpenAI(
        api_key=settings.openai_api_key,
        timeout=LLM_TIMEOUT_SEC,
        max_retries=LLM_MAX_RETRIES,
    )


@lru_cache(maxsize=1)
def _anthropic_client() -> Any | None:
    """키가 있으면 캐시된 AsyncAnthropic, 없으면 None."""
    if not settings.anthropic_api_key:
        return None
    from anthropic import AsyncAnthropic

    return AsyncAnthropic(
        api_key=settings.anthropic_api_key,
        timeout=LLM_TIMEOUT_SEC,
        max_retries=LLM_MAX_RETRIES,
    )
