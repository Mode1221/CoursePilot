"""LLM 연동. Function Calling 기반 조건 분해 (7-1).

OPENAI_API_KEY 가 없으면 규칙 기반 파서로 폴백한다.
모델 역할은 "문장 파싱 + 도구 호출"로 한정 — 사실 정보는 API가 제공(할루시네이션 차단).
"""
from __future__ import annotations

import json

from app.config import settings
from app.pipeline.decomposition import parse_constraints
from app.schemas import PlanConstraints, TravelMode

_TOOL = {
    "type": "function",
    "function": {
        "name": "set_constraints",
        "description": "사용자 문장에서 모임 코스 조건을 추출한다.",
        "parameters": {
            "type": "object",
            "properties": {
                "region": {"type": "string", "description": "지역명 예: 성수동"},
                "start_time": {"type": "string", "description": "HH:MM 24시간"},
                "end_time": {"type": "string", "description": "HH:MM 24시간"},
                "duration_min": {"type": "integer"},
                "max_travel_min": {"type": "integer"},
                "travel_mode": {"type": "string", "enum": ["walk", "car", "transit"]},
                "budget_max": {"type": "integer", "description": "원 단위 하드 제약"},
                "keywords": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
}


async def decompose(text: str) -> PlanConstraints:
    """자연어 → PlanConstraints. 키 없거나 실패 시 규칙 기반 폴백."""
    if not settings.openai_api_key:
        return parse_constraints(text)

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        resp = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": "모임/데이트 코스 조건 추출기. 명시된 값만 채운다."},
                {"role": "user", "content": text},
            ],
            tools=[_TOOL],
            tool_choice={"type": "function", "function": {"name": "set_constraints"}},
        )
        call = resp.choices[0].message.tool_calls[0]
        args = json.loads(call.function.arguments)
        return _to_constraints(args, text)
    except Exception:
        return parse_constraints(text)


def _to_constraints(args: dict, text: str) -> PlanConstraints:
    base = parse_constraints(text)  # 규칙 기반 결과를 기본값으로, LLM 값으로 덮어쓰기
    data = base.model_dump()
    for key in ("region", "duration_min", "max_travel_min", "budget_max"):
        if args.get(key) is not None:
            data[key] = args[key]
    if args.get("keywords"):
        data["keywords"] = args["keywords"]
    if args.get("travel_mode"):
        data["travel_mode"] = TravelMode(args["travel_mode"])
    for key in ("start_time", "end_time"):
        if args.get(key):
            data[key] = args[key]  # "HH:MM" → pydantic time 파싱
    return PlanConstraints.model_validate(data)
