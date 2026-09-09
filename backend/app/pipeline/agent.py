"""에이전틱 오케스트레이터 (7장 전체 흐름).

Decomposition → Tool-Use → Validation → 조건 완화 재시도 → Final.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.adapters.map_service import MapService
from app.constants import DEFAULT_REGION
from app.pipeline.llm import decompose
from app.pipeline.planner import desired_slots, plan_course
from app.schemas import Place, PlanConstraints, TimelineItem

MIN_VALID = 3  # 유효 후보가 이 개수 미만이면 조건 완화
MIN_USABLE = 2  # 이 정도면 "코스"로 쓸 만하다 — 더 물어보지 않는다


def _min_valid(constraints: PlanConstraints) -> int:
    """이 요청에서 "충분하다"고 볼 장소 수.

    사용자가 "2차까지"처럼 개수를 직접 말했으면 그 수를 넘길 이유가 없다.
    """
    if constraints.stop_count:
        return max(1, min(MIN_VALID, constraints.stop_count))
    return MIN_VALID


def _min_usable(constraints: PlanConstraints) -> int:
    """되묻지 않아도 되는 최소 장소 수.

    개수를 직접 말했으면 그 수가 기준이고, 아니면 2곳이면 코스로 쓸 만하다.
    3곳(MIN_VALID)에 못 미쳤다는 이유로 매번 "완화할까요?"를 띄우면
    정상 요청에도 확인 프롬프트가 뜬다.
    """
    if constraints.stop_count:
        return max(1, constraints.stop_count)
    return MIN_USABLE

# 완화해도 유지할 하드성 키워드(식이 제한 등 타협 불가)
_HARD_KEYWORDS = {"비건", "채식", "할랄", "글루텐프리", "노키즈", "실내"}

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
    force_relax: bool = False,
    exclude_place_ids: set[str] | None = None,
) -> PlanResult:
    """자연어 요청 → 코스.

    force_relax=True 면 원래 조건으로의 첫 시도를 건너뛰고 곧장 완화한다
    (사용자가 "조건을 완화해도 좋다"고 답한 뒤의 재시도용).
    """
    progress = on_progress or _noop

    await progress("decomposition")  # 문장 분해
    constraints = await decompose(text)
    if preferences:
        _apply_preferences(constraints, preferences)
    _apply_large_party(constraints)

    await progress("search")  # 후보 수집
    # 출발지 좌표는 재시도마다 바뀌지 않으므로 한 번만 조회한다(외부 호출 절약)
    origin = await _resolve_origin(constraints, map_service)
    timeline = await _attempt(constraints, map_service, origin, exclude_place_ids)
    await progress("validation")  # 물리 제약 검증

    enough = _min_valid(constraints)
    if len(timeline) >= enough and not force_relax:
        await progress("done")
        await _verify_hours(timeline)
        # 개수를 직접 말한 요청("5곳")에 못 미치면, 완화 없이 끝내더라도
        # 그 사실을 알리고 완화 여부를 물어본다(조용히 4곳만 주지 않는다).
        return PlanResult(
            constraints,
            timeline,
            relaxed=False,
            needs_confirmation=len(timeline) < _min_usable(constraints),
        )

    # 7-4 조건 완화: 소프트 제약(이동시간 여유폭)부터 단계적 완화. 하드 제약(예산)은 유지.
    # #16 학습: 완화 수용률이 높을수록 이동시간을 더 과감히(1.5~2.0x) 완화.
    await progress("relaxing")
    from app.feedback import feedback_store

    factor = 1.5 + 0.5 * feedback_store.acceptance_rate()  # 1.75 기본, 2.0 상한
    if force_relax:
        factor = 2.0  # 사용자가 완화에 동의했으므로 가장 과감한 폭을 쓴다
    base_len = len(timeline)  # 완화 없이 나온 결과. 이보다 나아졌을 때만 "완화했다"고 말한다
    best = timeline  # 완화가 되레 더 나쁠 수 있으므로 원래 결과를 기준선으로 둔다
    relaxed_c = constraints.model_copy(deep=True)
    if relaxed_c.max_travel_min is not None:
        relaxed_c.max_travel_min = int(relaxed_c.max_travel_min * factor)
    timeline = await _attempt(relaxed_c, map_service, origin, exclude_place_ids)
    if len(timeline) > len(best):
        best = timeline

    # 그래도 부족하면 소프트 키워드 제약을 완화(다이어트 등 하드성 키워드는 유지)
    if (len(best) < enough or force_relax) and relaxed_c.keywords:
        relaxed_c.keywords = [k for k in relaxed_c.keywords if k in _HARD_KEYWORDS]
        timeline = await _attempt(relaxed_c, map_service, origin, exclude_place_ids)
        if len(timeline) > len(best):
            best = timeline

    timeline = best
    # 완화 결과를 실제로 쓴 경우에만 완화했다고 알린다 — 바뀐 게 없는데
    # "일부 조건은 완화했어요"라고 하면 사용자는 무엇이 깎였는지 알 수 없다.
    relaxed = len(timeline) > base_len
    needs_confirmation = len(timeline) < _min_usable(constraints)
    await progress("done")
    await _verify_hours(timeline)
    return PlanResult(
        relaxed_c if relaxed else constraints,
        timeline,
        relaxed=relaxed,
        needs_confirmation=needs_confirmation,
    )


async def _verify_hours(timeline: list[TimelineItem]) -> None:
    """확정된 장소의 영업시간만 TTL 확인 후 갱신한다.

    후보 전체를 물으면 Google Pro 무료 한도(월 5,000)를 하루에 태운다.
    코스에 남은 3~5곳만, 그것도 30일 지난 것만 갱신한다. 실패해도 코스는 그대로다.
    """
    places = [item.place for item in timeline]
    try:
        from app.adapters.google import refresh_final_hours

        await refresh_final_hours(places)
    except Exception:
        pass
    # Google 에 영업시간이 없는 곳(관광지·전시관이 대부분)은 공공 데이터로 메운다.
    try:
        from app.adapters.tourapi import TourApiClient

        client = TourApiClient()
        if client.enabled:
            unverified = [p for p in places if p.hours_unverified]
            if unverified:
                await asyncio.gather(
                    *(client.enrich(p) for p in unverified), return_exceptions=True
                )
    except Exception:
        pass


# 온보딩 예산 문항 → 1인 예산 상한(원). 문항 값과 1:1 대응.
BUDGET_CHOICES: dict[str, int] = {
    "2만원 이하": 20000,
    "2~4만원": 40000,
    "4~6만원": 60000,
    "6만원 이상": 100000,
}


# 이 인원부터는 자리 자체가 제약이라 검색어에 반영한다(planner.LARGE_PARTY 와 동일 기준)
LARGE_PARTY_QUERY = "단체석"


def _apply_large_party(constraints: PlanConstraints) -> None:
    """대인원이면 단체석을 검색어 뒤에 덧붙인다(사용자가 이미 말했으면 그대로)."""
    from app.pipeline.planner import LARGE_PARTY

    if not constraints.party_size or constraints.party_size < LARGE_PARTY:
        return
    if any(k in ("룸", "단체", "단체석") for k in constraints.keywords):
        return
    constraints.keywords.append(LARGE_PARTY_QUERY)


def _apply_preferences(constraints: PlanConstraints, prefs: dict) -> None:
    """온보딩 선호 프로필로 미입력 조건을 자동 보완 (9-6). 명시값은 유지."""
    if not constraints.region and prefs.get("region"):
        constraints.region = prefs["region"]
    # 예산은 요청에 금액이 없을 때만 보완한다(문장에 적힌 금액이 항상 우선)
    if constraints.budget_max is None and prefs.get("budget") in BUDGET_CHOICES:
        constraints.budget_max = BUDGET_CHOICES[prefs["budget"]]
    if prefs.get("mood") and prefs["mood"] not in constraints.keywords:
        constraints.keywords.append(prefs["mood"])
    for diet in prefs.get("diet") or []:
        if diet not in constraints.keywords:
            constraints.keywords.append(diet)
    if prefs.get("transport") == "차량":
        from app.schemas import TravelMode

        constraints.travel_mode = TravelMode.CAR


MAX_QUERY_KEYWORDS = 3  # 지역 + 키워드 3개까지만 검색 질의로 전달
CANDIDATES_PER_SLOT = 6  # 칸마다 이 정도 후보가 있어야 카테고리·영업시간 필터를 견딘다
MAX_CANDIDATES = 40  # 6칸 코스(칸당 6후보)까지 채울 수 있는 상한


async def _attempt(
    constraints: PlanConstraints,
    map_service: MapService,
    origin: Place | None = None,
    exclude_place_ids: set[str] | None = None,
) -> list[TimelineItem]:
    region = constraints.region or DEFAULT_REGION
    # 검색어가 길수록 결과가 급감하므로 상위 몇 개만 질의에 쓴다(나머지는 스코어링에서 반영).
    query_keywords = constraints.keywords[:MAX_QUERY_KEYWORDS]
    # 칸 수가 많을수록 후보가 더 필요하다(영업시간·카테고리 필터로 상당수가 탈락)
    limit = min(MAX_CANDIDATES, max(10, len(desired_slots(constraints)) * CANDIDATES_PER_SLOT))
    candidates = await map_service.search_places(region, query_keywords, limit=limit)
    if exclude_place_ids:
        # "전부 다른 곳으로" — 지금 코스에 있는 장소는 후보에서 뺀다
        filtered = [p for p in candidates if p.id not in exclude_place_ids]
        if filtered:  # 전부 걸러지면 기존 후보라도 쓴다(빈 코스보다 낫다)
            candidates = filtered
    # 스코어링·카테고리 템플릿·동선·Best-of-N 으로 최적 코스 선택
    return await plan_course(candidates, constraints, map_service, origin=origin)


async def _resolve_origin(
    constraints: PlanConstraints, map_service: MapService
) -> Place | None:
    """출발지 문자열을 좌표로 변환. 실패하면 None(기존 동선 로직 유지)."""
    if not constraints.start_place:
        return None
    found = await map_service.search_places(constraints.start_place, [], limit=1)
    return found[0] if found else None
