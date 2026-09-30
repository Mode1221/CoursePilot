"""LLM 연동. 도구 호출(Function/Tool Calling) 기반 조건 분해 (7-1).

기본 프로바이더는 Anthropic Claude Haiku 4.5. 키 없거나 실패 시 규칙 기반 파서로 폴백.
모델 역할은 "문장 파싱 + 도구 호출"로 한정 — 사실 정보는 API가 제공(할루시네이션 차단).
"""
from __future__ import annotations

import json
import re

from app.config import settings
from app.pipeline.decomposition import parse_constraints
from app.schemas import PlanConstraints, TravelMode

_SYSTEM = "모임/데이트 코스 조건 추출기. 사용자 문장에 명시된 값만 채운다."
_TOOL_NAME = "set_constraints"
# 도구 파라미터 스키마(프로바이더 공통 JSON Schema)
_PARAMS = {
    "type": "object",
    "properties": {
        "region": {"type": "string", "description": "지역명 예: 성수동"},
        "start_time": {"type": "string", "description": "HH:MM 24시간"},
        "end_time": {"type": "string", "description": "HH:MM 24시간"},
        "duration_min": {"type": "integer"},
        "max_travel_min": {"type": "integer"},
        "travel_mode": {"type": "string", "enum": ["walk", "car", "transit"]},
        "budget_max": {"type": "integer", "description": "1인 기준 원 단위 하드 제약"},
        "party_size": {"type": "integer", "description": "참여 인원수"},
        "stop_count": {"type": "integer", "description": "방문할 장소 개수(예: 2차 → 2)"},
        "keywords": {"type": "array", "items": {"type": "string"}},
        "exclude_keywords": {
            "type": "array",
            "items": {"type": "string"},
            "description": "제외 조건 예: 술집 빼고 → [\"술집\"]",
        },
    },
}
# OpenAI Function Calling 포맷
_OPENAI_TOOL = {
    "type": "function",
    "function": {
        "name": _TOOL_NAME,
        "description": "사용자 문장에서 모임 코스 조건을 추출한다.",
        "parameters": _PARAMS,
    },
}
# Anthropic Tool Use 포맷
_ANTHROPIC_TOOL = {
    "name": _TOOL_NAME,
    "description": "사용자 문장에서 모임 코스 조건을 추출한다.",
    "input_schema": _PARAMS,
}


async def decompose(text: str) -> PlanConstraints:
    """자연어 → PlanConstraints. 키 없거나 실패 시 규칙 기반 폴백."""
    from app.metrics import metrics_store

    try:
        if settings.llm_provider == "openai":
            args = await _decompose_openai(text)
        else:
            args = await _decompose_anthropic(text)
    except Exception:
        args = None
    if args is None:
        # 키 미설정도 폴백으로 집계한다(실제로 규칙 파서가 쓰였다는 사실이 중요)
        metrics_store.record_external("llm.decompose", ok=False)
        return parse_constraints(text)
    metrics_store.record_external("llm.decompose", ok=True)
    return _to_constraints(args, text)


async def _decompose_anthropic(text: str) -> dict | None:
    from app.llm_client import get_anthropic_client

    client = get_anthropic_client()
    if client is None:
        return None
    from app.llm_client import anthropic_params

    resp = await client.messages.create(
        **anthropic_params(512, _SYSTEM, _TOOL_NAME, fast=True),
        tools=[_ANTHROPIC_TOOL],
        messages=[{"role": "user", "content": text}],
    )
    for block in resp.content:
        if block.type == "tool_use" and block.name == _TOOL_NAME:
            return dict(block.input)
    return None


async def _decompose_openai(text: str) -> dict | None:
    from app.llm_client import get_openai_client

    client = get_openai_client()
    if client is None:
        return None
    resp = await client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": text},
        ],
        tools=[_OPENAI_TOOL],
        tool_choice={"type": "function", "function": {"name": _TOOL_NAME}},
    )
    call = resp.choices[0].message.tool_calls[0]
    return json.loads(call.function.arguments)


# 문장에 없는 값을 LLM 이 "추정"하면 코스가 한두 곳으로 쪼그라들었다(운영 점검 2026-09-30, AI 켠 직후):
# "파스타 먹고 와인바" → 개수 2, "부모님 모시고 점심, 많이 안 걷게" → 이동 5분·짧은 소요 → 1곳.
# 개수·소요·종료 시각은 문장에 근거가 있을 때만 받고, 이동 상한은 너무 빡빡하지 않게 바닥을 둔다.
MIN_TRAVEL_FLOOR = 15
_DURATION_HINT = re.compile(r"\d+\s*(시간|분)|[한두세네]\s*시간|반나절|하루|종일")
_END_HINT = re.compile(r"까지")
_COUNT_HINT = re.compile(r"\d+\s*(곳|군데|차|개)|[한두세네]\s*(곳|군데|개)|다섯\s*(곳|군데)|\d\s*차|[이삼사]차")


def _guard(args: dict, base: PlanConstraints, text: str) -> dict:
    out = dict(args)
    if base.stop_count is None and not _COUNT_HINT.search(text):
        out.pop("stop_count", None)  # "N곳·N차·N군데"를 말하지 않았다
    if base.duration_min is None and not _DURATION_HINT.search(text):
        out.pop("duration_min", None)
    if base.end_time is None and not _END_HINT.search(text):
        out.pop("end_time", None)
    travel = out.get("max_travel_min")
    if travel is not None and base.max_travel_min is None:
        out["max_travel_min"] = max(int(travel), MIN_TRAVEL_FLOOR)
    return out


def _to_constraints(args: dict, text: str) -> PlanConstraints:
    base = parse_constraints(text)  # 규칙 기반 결과를 기본값으로, LLM 값으로 덮어쓰기
    data = base.model_dump()
    args = _guard(args, base, text)
    for key in (
        "region", "duration_min", "max_travel_min", "budget_max", "party_size", "stop_count"
    ):
        if args.get(key) is not None:
            data[key] = args[key]
    if args.get("keywords"):
        # 규칙 파서가 넣은 조건(우천 시 "실내" 등)이 사라지지 않도록 합친다
        merged = list(base.keywords)
        merged += [k for k in args["keywords"] if k not in merged]
        data["keywords"] = merged
    if args.get("exclude_keywords"):
        data["exclude_keywords"] = args["exclude_keywords"]
    if args.get("travel_mode"):
        data["travel_mode"] = TravelMode(args["travel_mode"])
    for key in ("start_time", "end_time"):
        if args.get(key):
            data[key] = args[key]  # "HH:MM" → pydantic time 파싱
    return PlanConstraints.model_validate(data)
