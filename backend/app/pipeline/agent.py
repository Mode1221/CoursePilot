"""에이전틱 오케스트레이터 (7장 전체 흐름).

Decomposition → Tool-Use → Validation → 조건 완화 재시도 → Final.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.adapters.map_service import MapService
from app.constants import DEFAULT_REGION
from app.pipeline.llm import decompose
from app.pipeline.planner import plan_course
from app.schemas import PlanConstraints, TimelineItem

MIN_VALID = 3  # 유효 후보가 이 개수 미만이면 조건 완화

# 완화해도 유지할 하드성 키워드(식이 제한 등 타협 불가)
_HARD_KEYWORDS = {"비건", "채식", "할랄", "글루텐프리", "노키즈"}

# 진행 단계 콜백 (5-4 실시간 상태 표시). 미지정 시 무동작.
ProgressFn = Callable[[str], Awaitable[None]]


async def _noop(_stage: str) -> None:
    pass


@dataclass
class PlanResult:
    constraints: PlanConstraints
    timeline: list[TimelineItem]
    relaxed: bool  # 조건 완화가 적용됐는지
    needs_confirmation: bool  # 완화로도 부족 → 사용자 확인 필요


async def generate_course(
    text: str,
    map_service: MapService,
    preferences: dict | None = None,
    on_progress: ProgressFn | None = None,
) -> PlanResult:
    progress = on_progress or _noop

    await progress("decomposition")  # 문장 분해
    constraints = await decompose(text)
    if preferences:
        _apply_preferences(constraints, preferences)

    await progress("search")  # 후보 수집
    timeline = await _attempt(constraints, map_service)
    await progress("validation")  # 물리 제약 검증

    if len(timeline) >= MIN_VALID:
        await progress("done")
        return PlanResult(constraints, timeline, relaxed=False, needs_confirmation=False)

    # 7-4 조건 완화: 소프트 제약(이동시간 여유폭)부터 단계적 완화. 하드 제약(예산)은 유지.
    # #16 학습: 완화 수용률이 높을수록 이동시간을 더 과감히(1.5~2.0x) 완화.
    await progress("relaxing")
    from app.feedback import feedback_store

    factor = 1.5 + 0.5 * feedback_store.acceptance_rate()  # 1.75 기본, 2.0 상한
    relaxed_c = constraints.model_copy(deep=True)
    if relaxed_c.max_travel_min is not None:
        relaxed_c.max_travel_min = int(relaxed_c.max_travel_min * factor)
    timeline = await _attempt(relaxed_c, map_service)

    # 그래도 부족하면 소프트 키워드 제약을 완화(다이어트 등 하드성 키워드는 유지)
    if len(timeline) < MIN_VALID and relaxed_c.keywords:
        relaxed_c.keywords = [k for k in relaxed_c.keywords if k in _HARD_KEYWORDS]
        timeline = await _attempt(relaxed_c, map_service)

    needs_confirmation = len(timeline) < MIN_VALID
    await progress("done")
    return PlanResult(relaxed_c, timeline, relaxed=True, needs_confirmation=needs_confirmation)


def _apply_preferences(constraints: PlanConstraints, prefs: dict) -> None:
    """온보딩 선호 프로필로 미입력 조건을 자동 보완 (9-6). 명시값은 유지."""
    if not constraints.region and prefs.get("region"):
        constraints.region = prefs["region"]
    if prefs.get("mood") and prefs["mood"] not in constraints.keywords:
        constraints.keywords.append(prefs["mood"])
    for diet in prefs.get("diet") or []:
        if diet not in constraints.keywords:
            constraints.keywords.append(diet)
    if prefs.get("transport") == "차량":
        from app.schemas import TravelMode

        constraints.travel_mode = TravelMode.CAR


MAX_QUERY_KEYWORDS = 3  # 지역 + 키워드 3개까지만 검색 질의로 전달


async def _attempt(
    constraints: PlanConstraints, map_service: MapService
) -> list[TimelineItem]:
    region = constraints.region or DEFAULT_REGION
    # 검색어가 길수록 결과가 급감하므로 상위 몇 개만 질의에 쓴다(나머지는 스코어링에서 반영).
    query_keywords = constraints.keywords[:MAX_QUERY_KEYWORDS]
    candidates = await map_service.search_places(region, query_keywords, limit=10)
    # 스코어링·카테고리 템플릿·동선·Best-of-N 으로 최적 코스 선택
    return await plan_course(candidates, constraints, map_service)
