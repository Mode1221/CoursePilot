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


# effort 를 쓰면 생각 토큰도 max_tokens 안에 들어간다 — 짧은 답이라도 생각할 자리를 준다.
# 실측(scripts/llm_bench.py, 2026-09-30): 조건 분해 1회 출력 Sonnet 5.5 high 214·Opus 5.5 high 309·Fable 5.1 high 351 토큰.
THINKING_ROOM = 4_000


def _supports_forced_tool(model: str) -> bool:
    """도구 강제 호출(tool_choice=tool). 5.x 세대(Sonnet 5.5 등)는 받지 않아 400 이 난다."""
    return model.startswith("claude-haiku") or model.startswith("claude-3") or "-4-" in model


def _supports_effort(model: str) -> bool:
    return not model.startswith("claude-haiku") and not model.startswith("claude-3")


def anthropic_params(
    max_tokens: int, system: str | None = None, tool: str | None = None, *, fast: bool = False
) -> dict:
    """Anthropic 호출 공통 인자 — 모델·effort·도구 강제 여부를 설정 하나로 맞춘다.

    `ANTHROPIC_MODEL`/`ANTHROPIC_EFFORT` 만 바꾸면 모든 호출부가 따라온다. 강제 호출을 못 쓰는 모델이면
    `auto` + "반드시 도구로 답하라"는 지시로 바꾼다(실측 5/5 도구 호출).

    fast=True 는 자주 불리는 단순 작업(조건 분해·영업시간 웹검색) — `ANTHROPIC_MODEL_FAST` 가 있으면 그 모델.
    실측에서 조건 분해는 Haiku 4.5 와 Sonnet 5.5 high 결과가 같았고 Haiku 가 1.5초 빨랐다.
    """
    model = (settings.anthropic_model_fast if fast else "") or settings.anthropic_model
    effort = (settings.anthropic_effort or "").strip().lower()
    use_effort = bool(effort) and _supports_effort(model)
    # effort 를 비워도 5.x 는 기본이 high 라 생각한다 — 자리는 늘 준다
    params: dict = {"model": model, "max_tokens": max_tokens + (THINKING_ROOM if _supports_effort(model) else 0)}
    if use_effort:
        params["extra_body"] = {"output_config": {"effort": effort}}
    if tool is not None:
        if _supports_forced_tool(model):
            params["tool_choice"] = {"type": "tool", "name": tool}
        else:
            params["tool_choice"] = {"type": "auto"}
            system = f"{system or ''} 반드시 {tool} 도구 한 번으로 답한다.".strip()
    if system:
        params["system"] = system
    return params
