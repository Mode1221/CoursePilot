"""영업시간 최후 폴백 — LLM 웹검색.

Google 에도 TourAPI 에도 영업시간이 없을 때만 쓴다. 부정확하고 느리고 비싸므로
1차 원천으로는 절대 쓰지 않으며, 결과는 항상 "확인 필요"로 표시한 채 반영한다.
코스당 호출 수에도 상한을 둔다.
"""
from __future__ import annotations

import asyncio
import json
import re
from datetime import time

from app.config import settings
from app.schemas import Place

MAX_LOOKUPS_PER_COURSE = 2  # 느리고 비싸다 — 코스당 이 개수까지만
_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")

_PROMPT = (
    "다음 장소의 오늘 영업 시작·종료 시각을 웹에서 확인해 JSON 한 줄로만 답해라.\n"
    '형식: {{"open": "HH:MM", "close": "HH:MM"}} / 확실하지 않으면 {{"open": null, "close": null}}\n'
    "장소: {name}\n주소: {address}"
)


def parse_hours(text: str) -> tuple[time, time] | None:
    """모델 응답에서 영업시간 JSON 을 뽑는다. 형식이 어긋나면 None."""
    match = re.search(r"\{[^{}]*\}", text or "")
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except ValueError:
        return None
    open_raw, close_raw = data.get("open"), data.get("close")
    if not isinstance(open_raw, str) or not isinstance(close_raw, str):
        return None
    if not (_TIME_RE.match(open_raw) and _TIME_RE.match(close_raw)):
        return None
    return time.fromisoformat(open_raw), time.fromisoformat(close_raw)


async def _lookup(place: Place) -> tuple[time, time] | None:
    from app.llm_client import get_anthropic_client

    client = get_anthropic_client()
    if client is None:
        return None
    resp = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=256,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 2}],
        messages=[
            {
                "role": "user",
                "content": _PROMPT.format(name=place.name, address=place.address or ""),
            }
        ],
    )
    text = "".join(
        block.text for block in resp.content if getattr(block, "type", "") == "text"
    )
    return parse_hours(text)


async def fill_missing_hours(
    places: list[Place], limit: int = MAX_LOOKUPS_PER_COURSE
) -> int:
    """영업시간을 못 구한 장소만 웹검색으로 메운다. 결과는 '확인 필요'로 남긴다."""
    if not settings.anthropic_api_key:
        return 0
    targets = [p for p in places if p.hours_unverified and p.open_time is None][:limit]
    if not targets:
        return 0
    results = await asyncio.gather(
        *(_lookup(p) for p in targets), return_exceptions=True
    )
    filled = 0
    for place, result in zip(targets, results, strict=False):
        if isinstance(result, tuple):
            place.open_time, place.close_time = result
            # 웹검색 결과는 확정으로 보지 않는다 — 사용자에게 확인을 권한다.
            place.hours_unverified = True
            filled += 1
    return filled
