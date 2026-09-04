"""에이전틱 오케스트레이터 (7장 전체 흐름).

Decomposition → Tool-Use → Validation → 조건 완화 재시도 → Final.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.adapters.map_service import MapService
from app.pipeline.llm import decompose
from app.pipeline.validation import build_timeline
from app.schemas import PlanConstraints, TimelineItem

MIN_VALID = 3  # 유효 후보가 이 개수 미만이면 조건 완화


@dataclass
class PlanResult:
    constraints: PlanConstraints
    timeline: list[TimelineItem]
    relaxed: bool  # 조건 완화가 적용됐는지
    needs_confirmation: bool  # 완화로도 부족 → 사용자 확인 필요


async def generate_course(text: str, map_service: MapService) -> PlanResult:
    constraints = await decompose(text)

    timeline, relaxed = await _attempt(constraints, map_service)

    if len(timeline) >= MIN_VALID:
        return PlanResult(constraints, timeline, relaxed, needs_confirmation=False)

    # 7-4 조건 완화: 소프트 제약(이동시간 여유폭)부터 단계적 완화. 하드 제약(예산)은 유지.
    relaxed_c = constraints.model_copy(deep=True)
    if relaxed_c.max_travel_min is not None:
        relaxed_c.max_travel_min = int(relaxed_c.max_travel_min * 1.5)
    timeline, _ = await _attempt(relaxed_c, map_service)

    needs_confirmation = len(timeline) < MIN_VALID
    return PlanResult(relaxed_c, timeline, relaxed=True, needs_confirmation=needs_confirmation)


async def _attempt(
    constraints: PlanConstraints, map_service: MapService
) -> tuple[list[TimelineItem], bool]:
    region = constraints.region or "성수동"
    candidates = await map_service.search_places(region, constraints.keywords, limit=10)
    timeline = await build_timeline(candidates, constraints, map_service)
    return timeline, False
