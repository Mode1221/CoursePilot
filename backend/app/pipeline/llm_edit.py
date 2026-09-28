"""채팅 코스 수정 요청을 LLM 으로 해석한다.

규칙 파서(`edit.parse_edit`)는 정해진 표현("2번 바꿔줘", "카페 빼줘")만 알아듣는다.
"카페 대신 산책할 데", "밥집 좀 더 분위기 있는 데로", "너무 비싸" 같은 말은 놓치거나
엉뚱하게 해석해(카페를 하나 더 넣거나, 새 코스를 만들려다 되묻는다) 수정이 안 되는 것처럼 보였다.

LLM 은 지금 코스 목록을 보고 **무엇을 어디에** 할지만 정한다(도구 호출 한 번).
장소 자체는 고르지 않는다 — 검색어만 내고 실제 장소는 지도 어댑터가 준다(할루시네이션 차단).
키가 없거나 실패하면 None → 규칙 파서 결과를 그대로 쓴다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from app.config import settings
from app.pipeline.edit import EditCommand
from app.schemas import TimelineItem

_TOOL = "edit_course"
_SYSTEM = (
    "데이트 코스 수정 요청 해석기. 번호가 붙은 현재 코스와 사용자 요청을 보고 edit_course 를 한 번 호출한다.\n"
    "- replace: 특정 자리를 다른 곳으로. positions 에 그 자리, search 에 새로 찾을 곳의 검색어"
    "(예: '조용한 카페', '공원', '분위기 좋은 파스타').\n"
    "- remove: positions 의 자리를 뺀다.\n"
    "- add: search 로 찾은 곳을 끼워 넣는다. positions 가 있으면 그 자리 앞, 없으면 맨 뒤.\n"
    "- swap: positions 두 자리를 맞바꾼다. reorder: 동선이 짧게 순서만 다시.\n"
    "- condition: 특정 자리가 아니라 코스 전체의 조건을 바꾸라는 말(예: '너무 비싸' → condition '저렴한', "
    "'다 너무 멀어' → '가까운', '전체적으로 조용한 데로' → '조용한'). condition 에 조건 문구.\n"
    "- new_course: 다른 지역·다른 모임으로 새로 짜 달라는 말. question: 코스에 대한 질문. none: 그 밖.\n"
    "자리를 이름·종류로 말했으면(예: '카페 대신') 목록에서 찾아 번호로 바꾼다. 번호는 1부터."
)
_PARAMS = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["replace", "remove", "add", "swap", "reorder", "condition", "new_course", "question", "none"],
        },
        "positions": {"type": "array", "items": {"type": "integer"}},
        "search": {"type": "string"},
        "condition": {"type": "string"},
    },
    "required": ["action"],
}


@dataclass
class ConditionChange:
    """코스 전체 조건 변경 — 직전 조건에 덧붙여 다시 만든다."""

    text: str


def _course_lines(items: list[TimelineItem]) -> str:
    return "\n".join(
        f"{i}. {it.place.name} ({it.place.category or '분류 없음'})" for i, it in enumerate(items, 1)
    )


def to_command(args: dict, length: int) -> EditCommand | ConditionChange | None:
    """도구 인자 → 편집 명령. 범위를 벗어난 번호는 버린다(모델이 틀려도 엉뚱한 칸을 건드리지 않게)."""
    action = args.get("action")
    pos = [p - 1 for p in args.get("positions") or [] if isinstance(p, int) and 1 <= p <= length]
    search = str(args.get("search") or "").strip()
    if action == "condition":
        cond = str(args.get("condition") or "").strip()
        return ConditionChange(cond) if cond else None
    if action == "replace" and pos:
        return EditCommand(action="replace", index=pos[0], keyword=search)
    if action == "remove" and pos:
        return EditCommand(action="remove", index=pos[0], indexes=pos if len(pos) > 1 else [])
    if action == "add" and search:
        return EditCommand(action="add", index=pos[0] if pos else -1, keyword=search)
    if action == "swap" and len(pos) >= 2 and pos[0] != pos[1]:
        return EditCommand(action="swap", index=pos[0], index2=pos[1])
    if action == "reorder":
        return EditCommand(action="reorder")
    return None


async def interpret_edit(text: str, items: list[TimelineItem]) -> EditCommand | ConditionChange | None:
    from app.metrics import metrics_store

    if not items:
        return None
    prompt = f"현재 코스:\n{_course_lines(items)}\n\n요청: {text}"
    try:
        if settings.llm_provider == "openai":
            args = await _call_openai(prompt)
        else:
            args = await _call_anthropic(prompt)
    except Exception:
        args = None
    metrics_store.record_external("llm.edit", ok=args is not None)
    if args is None:
        return None
    return to_command(args, len(items))


async def _call_anthropic(prompt: str) -> dict | None:
    from app.llm_client import get_anthropic_client

    client = get_anthropic_client()
    if client is None:
        return None
    resp = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=256,
        system=_SYSTEM,
        tools=[{"name": _TOOL, "description": "코스 수정 방법을 정한다.", "input_schema": _PARAMS}],
        tool_choice={"type": "tool", "name": _TOOL},
        messages=[{"role": "user", "content": prompt}],
    )
    for block in resp.content:
        if block.type == "tool_use" and block.name == _TOOL:
            return dict(block.input)
    return None


async def _call_openai(prompt: str) -> dict | None:
    from app.llm_client import get_openai_client

    client = get_openai_client()
    if client is None:
        return None
    resp = await client.chat.completions.create(
        model=settings.openai_model,
        messages=[{"role": "system", "content": _SYSTEM}, {"role": "user", "content": prompt}],
        tools=[{"type": "function", "function": {"name": _TOOL, "description": "코스 수정 방법을 정한다.", "parameters": _PARAMS}}],
        tool_choice={"type": "function", "function": {"name": _TOOL}},
    )
    call = resp.choices[0].message.tool_calls[0]
    return json.loads(call.function.arguments)
