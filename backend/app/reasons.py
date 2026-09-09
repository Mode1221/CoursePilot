"""코스에 이 장소가 들어간 이유 (설명 가능성).

추천을 그대로 받아들이라고 하는 대신, 어떤 근거로 골랐는지 짧게 보여준다.
저장하지 않고 코스 상태 + 마지막 요청 문장으로 그때그때 계산한다.
"""
from __future__ import annotations

from app.schemas import Course, PlanConstraints, TimelineItem

GOOD_RATING = 4.3  # 이 이상이면 "평점 좋음"으로 언급할 만하다
NEAR_MIN = 10  # 이 시간 이하로 이어지면 "가깝다"고 말할 수 있다


def _place_reasons(
    item: TimelineItem,
    prev: TimelineItem | None,
    constraints: PlanConstraints,
    context_pop: float,
) -> list[str]:
    reasons: list[str] = []
    haystack = f"{item.place.category or ''} {item.place.name}".lower()

    matched = [k for k in constraints.keywords if k.lower() in haystack]
    if matched:
        reasons.append(f"'{matched[0]}' 조건에 맞아요")

    if item.place.rating is not None and item.place.rating >= GOOD_RATING:
        reasons.append(f"평점 {item.place.rating}")

    if constraints.budget_max and item.place.price is not None:
        if item.place.price <= constraints.budget_max:
            reasons.append(f"1인 {item.place.price // 1000}천원대로 예산 안")

    if prev is not None and prev.travel_to_next is not None:
        mins = prev.travel_to_next.duration_min
        if mins <= NEAR_MIN:
            reasons.append(f"앞 장소에서 {mins}분")

    if context_pop >= 0.8:
        reasons.append("이 시간대에 자주 선택돼요")

    return reasons


def course_reasons(course: Course, text: str) -> dict[str, list[str]]:
    """장소 id → 근거 문구들. 근거가 없으면 빈 목록."""
    from app.pipeline.decomposition import parse_constraints
    from app.timecontext import daypart_of, time_context_store

    constraints = parse_constraints(text or "")
    ids = [it.place.id for it in course.items]
    hour = course.items[0].arrive.hour if course.items and course.items[0].arrive else 12
    raw = time_context_store.scores(ids, daypart_of(hour))
    peak = max(raw.values(), default=0.0)

    out: dict[str, list[str]] = {}
    prev: TimelineItem | None = None
    for item in course.items:
        ctx = (raw.get(item.place.id, 0.0) / peak) if peak else 0.0
        out[item.place.id] = _place_reasons(item, prev, constraints, ctx)
        prev = item
    return out
