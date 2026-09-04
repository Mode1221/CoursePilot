"""부분 수정 명령 파싱 및 적용 (4-3 AI 제어).

"두 번째 카페 말고 빵집으로 바꿔줘" → 해당 카드만 교체 후 전체 동선 재계산.
규칙 기반 파서(오프라인/폴백). 순서 인식 실패 시 action=none.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import time

from app.adapters.map_service import MapService
from app.pipeline.validation import recompute
from app.schemas import Course, TimelineItem, TravelMode

_ORDINALS = {
    "첫": 1, "두": 2, "세": 3, "네": 4, "다섯": 5,
    "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9, "열": 10,
}
_REPLACE_RE = re.compile(r"(바꿔|교체|변경)")
_REMOVE_RE = re.compile(r"(빼|삭제|제거|없애)")
# 교체 대상 키워드: "빵집으로", "카페로" 등 조사 앞 명사
_TARGET_RE = re.compile(r"([가-힣A-Za-z]+?)(?:으로|로)\s*(?:바꿔|교체|변경)")


@dataclass
class EditCommand:
    action: str  # "replace" | "remove" | "none"
    index: int = -1  # 0-based
    keyword: str = ""


def parse_edit(text: str) -> EditCommand:
    idx = _find_index(text)
    if idx < 0:
        return EditCommand(action="none")

    if _REPLACE_RE.search(text):
        m = _TARGET_RE.search(text)
        keyword = m.group(1) if m else ""
        return EditCommand(action="replace", index=idx, keyword=keyword)
    if _REMOVE_RE.search(text):
        return EditCommand(action="remove", index=idx)
    return EditCommand(action="none")


def _find_index(text: str) -> int:
    # "3번째" 처럼 숫자
    m = re.search(r"(\d+)\s*번째", text)
    if m:
        return int(m.group(1)) - 1
    # "두 번째" 처럼 한글 서수
    for word, n in _ORDINALS.items():
        if re.search(word + r"\s*번째", text):
            return n - 1
    return -1


async def apply_edit(
    course: Course, cmd: EditCommand, map_service: MapService
) -> list[TimelineItem]:
    """편집 명령을 적용해 갱신된 타임라인을 반환. 전체 동선 재계산."""
    items = list(course.items)
    if not (0 <= cmd.index < len(items)):
        return items

    if cmd.action == "remove":
        items.pop(cmd.index)
    elif cmd.action == "replace":
        existing_ids = {it.place.id for it in items}
        region = course.region or "성수동"
        candidates = await map_service.search_places(
            region, [cmd.keyword] if cmd.keyword else [], limit=10
        )
        replacement = next((p for p in candidates if p.id not in existing_ids), None)
        if replacement is None:
            return items
        items[cmd.index] = TimelineItem(place=replacement)

    start = items[0].arrive if items and items[0].arrive else time(12, 0)
    mode = _infer_mode(items)
    return await recompute([it.place for it in items], start, mode, map_service)


def _infer_mode(items: list[TimelineItem]) -> TravelMode:
    for it in items:
        if it.travel_to_next:
            return it.travel_to_next.mode
    return TravelMode.WALK
