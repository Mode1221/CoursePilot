"""부분 수정 명령 파싱 및 적용 (4-3 AI 제어).

"두 번째 카페 말고 빵집으로 바꿔줘" → 해당 카드만 교체 후 전체 동선 재계산.
규칙 기반 파서(오프라인/폴백). 순서 인식 실패 시 action=none.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.adapters.map_service import MapService
from app.constants import DEFAULT_REGION, DEFAULT_START_TIME
from app.pipeline.validation import recompute
from app.schemas import Course, TimelineItem, TravelMode

_ORDINALS = {
    "첫": 1, "두": 2, "세": 3, "네": 4, "다섯": 5,
    "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9, "열": 10,
}
# "다른 곳으로", "딴 데로" 처럼 동사 없이 교체를 뜻하는 표현도 받는다.
_REPLACE_RE = re.compile(r"(바꿔|바꾸|교체|변경|다른\s*(?:곳|데|장소)|딴\s*(?:곳|데))")
_REMOVE_RE = re.compile(r"(빼|삭제|제거|없애)")
# "카페 하나 추가해줘", "술집 넣어줘" → 전체 재생성 대신 한 칸만 덧붙인다
_ADD_RE = re.compile(r"(추가|넣어|붙여|더\s*가|하나\s*더)")
# 교체 대상 키워드: "빵집으로", "카페로" 등 조사 앞 명사
_TARGET_RE = re.compile(r"([가-힣A-Za-z]+?)(?:으로|로)\s*(?:바꿔|교체|변경)")


@dataclass
class EditCommand:
    action: str  # "replace" | "remove" | "add" | "none"
    index: int = -1  # 0-based
    keyword: str = ""
    match: str = ""  # 순서 대신 이름/카테고리로 지목한 경우("카페 빼줘")


# 순서 없이 이름·카테고리로 지목한 경우(코스를 봐야 위치를 안다)
MATCH_INDEX = -3
# 카테고리를 가리키는 일상 표현 → Place.category
_CATEGORY_WORDS = {
    "카페": "cafe",
    "커피": "cafe",
    "식당": "restaurant",
    "맛집": "restaurant",
    "밥집": "restaurant",
    "술집": "bar",
    "바": "bar",
    "포차": "bar",
}


def parse_edit(text: str) -> EditCommand:
    idx = _find_index(text)
    match = ""
    # 추가는 순서 지목이 없어도 성립한다(맨 뒤에 덧붙임)
    if _ADD_RE.search(text) and not _REPLACE_RE.search(text) and not _REMOVE_RE.search(text):
        keyword = next((w for w in _CATEGORY_WORDS if w in text), "")
        if keyword:
            return EditCommand(action="add", keyword=keyword, match=_CATEGORY_WORDS[keyword])
    if idx < 0 and idx != LAST_INDEX:
        # 순서를 못 찾았으면 "카페 빼줘"처럼 카테고리로 지목했는지 본다
        match = next((cat for word, cat in _CATEGORY_WORDS.items() if word in text), "")
        if not match:
            return EditCommand(action="none")
        idx = MATCH_INDEX

    if _REPLACE_RE.search(text):
        m = _TARGET_RE.search(text)
        keyword = m.group(1) if m else ""
        return EditCommand(action="replace", index=idx, keyword=keyword, match=match)
    if _REMOVE_RE.search(text):
        return EditCommand(action="remove", index=idx, match=match)
    return EditCommand(action="none")


# "마지막"은 호출측에서 코스 길이를 알아야 하므로 특별값으로 표시
LAST_INDEX = -2


def _find_index(text: str) -> int:
    # "3번째" / "3번" 처럼 숫자
    m = re.search(r"(\d+)\s*번(?:째)?", text)
    if m:
        return int(m.group(1)) - 1
    # "두 번째" 처럼 한글 서수 ("번째" 없이 "두 번" 도 허용)
    for word, n in _ORDINALS.items():
        if re.search(word + r"\s*번(?:째)?", text):
            return n - 1
    if "마지막" in text:
        return LAST_INDEX
    if re.search(r"처음|맨\s*앞", text):
        return 0
    return -1


async def apply_edit(
    course: Course, cmd: EditCommand, map_service: MapService
) -> list[TimelineItem]:
    """편집 명령을 적용해 갱신된 타임라인을 반환. 전체 동선 재계산."""
    items = list(course.items)
    if cmd.action == "add":
        return await _apply_add(course, items, cmd, map_service)
    if cmd.index == MATCH_INDEX:
        index = next(
            (i for i, it in enumerate(items) if it.place.category == cmd.match),
            -1,
        )
    elif cmd.index == LAST_INDEX:
        index = len(items) - 1
    else:
        index = cmd.index
    if not (0 <= index < len(items)):
        return items

    if cmd.action == "remove":
        items.pop(index)
    elif cmd.action == "replace":
        existing_ids = {it.place.id for it in items}
        region = course.region or DEFAULT_REGION
        candidates = await map_service.search_places(
            region, [cmd.keyword] if cmd.keyword else [], limit=10
        )
        fresh = [p for p in candidates if p.id not in existing_ids]
        # 교체는 그 자리의 성격을 유지해야 한다(카페 자리에 식당이 오면 코스가 망가짐)
        current_category = items[index].place.category
        replacement = next(
            (p for p in fresh if p.category == current_category),
            fresh[0] if fresh else None,
        )
        if replacement is None:
            return items
        items[index] = TimelineItem(place=replacement)

    start = items[0].arrive if items and items[0].arrive else DEFAULT_START_TIME
    mode = _infer_mode(items)
    return await recompute([it.place for it in items], start, mode, map_service)


async def _apply_add(
    course: Course,
    items: list[TimelineItem],
    cmd: EditCommand,
    map_service: MapService,
) -> list[TimelineItem]:
    """요청한 성격의 장소를 코스 맨 뒤에 한 칸 덧붙인다."""
    existing_ids = {it.place.id for it in items}
    region = course.region or DEFAULT_REGION
    candidates = await map_service.search_places(region, [cmd.keyword], limit=10)
    fresh = [p for p in candidates if p.id not in existing_ids]
    if not fresh:
        return items
    pick = next((p for p in fresh if p.category == cmd.match), fresh[0])
    items = [*items, TimelineItem(place=pick)]
    start = items[0].arrive if items[0].arrive else DEFAULT_START_TIME
    return await recompute([it.place for it in items], start, _infer_mode(items), map_service)


def _infer_mode(items: list[TimelineItem]) -> TravelMode:
    for it in items:
        if it.travel_to_next:
            return it.travel_to_next.mode
    return TravelMode.WALK
