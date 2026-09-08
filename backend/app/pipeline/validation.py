"""물리적 제약 검증 (7-3) 및 타임라인 계산."""
from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timedelta

from app.adapters.map_service import MapService
from app.constants import DEFAULT_START_TIME
from app.schemas import Place, PlanConstraints, Route, TimelineItem, TravelMode


def _overlaps_break(t: time, place: Place) -> bool:
    """방문 시각이 브레이크 타임에 걸리는지."""
    if place.break_start and place.break_end:
        return place.break_start <= t < place.break_end
    return False


def stay_minutes(place: Place) -> int:
    """카테고리별 기본 체류시간. 식당은 길게, 카페/전시는 보통."""
    cat = (place.category or "").lower()
    if any(k in cat for k in ("restaurant", "식당", "음식", "고기", "한식", "일식", "중식")):
        return 90
    if any(k in cat for k in ("bar", "술", "펍", "포차")):
        return 120
    return 60  # 카페·전시·기타


def _is_overnight(place: Place) -> bool:
    """새벽에 닫는 영업시간(예: 18:00~02:00)인지."""
    return bool(place.open_time and place.close_time and place.close_time <= place.open_time)


def is_open_at(place: Place, t: time) -> bool:
    """해당 시각에 영업 중인지 (영업시간 + 브레이크 타임 반영)."""
    if _is_overnight(place):
        # 자정을 넘겨 영업: 개점 이후이거나 마감 이전(다음 날 새벽)이면 영업 중
        if not (t >= place.open_time or t < place.close_time):
            return False
        return not _overlaps_break(t, place)
    if place.open_time and t < place.open_time:
        return False
    if place.close_time and t >= place.close_time:
        return False
    return not _overlaps_break(t, place)


def is_open_during(place: Place, arrive: time, depart: time) -> bool:
    """도착~출발 체류 구간 전체가 영업 중인지 검증.

    도착 시 영업 + 폐점 전 출발 + 체류 중 브레이크 진입 없음.
    """
    if not is_open_at(place, arrive):
        return False
    if _is_overnight(place):
        # 새벽 마감: 출발 시각도 영업 구간 안이어야 하고, 체류가 하루를 넘지 않아야 한다
        if not (depart > arrive or depart <= place.close_time):
            return False
        if depart > arrive and depart > place.close_time and depart <= place.open_time:
            return False
    elif place.close_time and depart > place.close_time:
        return False  # 체류가 폐점 시각을 넘김
    if place.break_start and place.break_end:
        # 체류 구간이 브레이크 시작과 겹치면 폐기 (arrive < break_start < depart)
        if arrive < place.break_start < depart:
            return False
    return True


async def build_timeline(
    places: list[Place],
    constraints: PlanConstraints,
    map_service: MapService,
) -> list[TimelineItem]:
    """후보 장소를 순서대로 배치하며 이동시간/영업시간을 검증한 타임라인 생성.

    조건 위반 장소는 폐기(스킵)한다.
    """
    mode = constraints.travel_mode
    cursor = _as_datetime(constraints.start_time or DEFAULT_START_TIME)
    end_dt = _as_datetime(constraints.end_time) if constraints.end_time else None

    timeline: list[TimelineItem] = []
    prev: Place | None = None
    spent = 0  # 누적 예상 비용(예산 하드 제약)

    for place in places:
        # 예산 하드 제약: 누적 비용이 상한을 넘으면 폐기 (가격 미상 장소는 통과)
        if (
            constraints.budget_max is not None
            and place.price is not None
            and spent + place.price > constraints.budget_max
        ):
            continue

        # 이전 장소로부터 이동. 아직 cursor 는 진전시키지 않는다(스킵 시 드리프트 방지).
        route: Route | None = None
        arrive_dt = cursor
        if prev is not None:
            route = await map_service.get_route(prev, place, mode)
            if (
                constraints.max_travel_min is not None
                and route.duration_min > constraints.max_travel_min
            ):
                continue  # 이동시간 조건 위반 → 폐기 (cursor 유지)
            arrive_dt = cursor + timedelta(minutes=route.duration_min)

        arrive = arrive_dt.time()
        depart_dt = arrive_dt + timedelta(minutes=stay_minutes(place))
        if not is_open_during(place, arrive, depart_dt.time()):
            continue  # 도착~출발 체류가 영업시간/브레이크 위반 → 폐기 (cursor 유지)

        if end_dt is not None and depart_dt > end_dt:
            break  # 전체 시간 초과 → 종료

        if timeline and route is not None:
            timeline[-1].travel_to_next = route

        timeline.append(
            TimelineItem(place=place, arrive=arrive, depart=depart_dt.time())
        )
        cursor = depart_dt  # 확정된 경우에만 진전
        spent += place.price or 0
        prev = place

    return timeline


async def recompute(
    places: list[Place],
    start_time: time,
    mode: TravelMode,
    map_service: MapService,
) -> list[TimelineItem]:
    """주어진 장소 순서를 그대로 유지하며 도착/출발/이동만 재계산한다(드롭 없음).

    수동 편집·부분 교체 후 동기화용 (4-3). 체류시간은 카테고리별로 계산.
    """
    # 구간 순서는 고정이고 각 경로 계산은 서로 독립 → 병렬 조회 후 순차 배치
    routes: list[Route] = []
    if len(places) > 1:
        routes = await asyncio.gather(
            *(
                map_service.get_route(places[i], places[i + 1], mode)
                for i in range(len(places) - 1)
            )
        )

    cursor = _as_datetime(start_time)
    timeline: list[TimelineItem] = []
    for i, place in enumerate(places):
        if i > 0:
            cursor = cursor + timedelta(minutes=routes[i - 1].duration_min)
            timeline[-1].travel_to_next = routes[i - 1]
        arrive = cursor.time()
        depart_dt = cursor + timedelta(minutes=stay_minutes(place))
        timeline.append(TimelineItem(place=place, arrive=arrive, depart=depart_dt.time()))
        cursor = depart_dt

    return timeline


def _as_datetime(t: time) -> datetime:
    return datetime.combine(date.today(), t)
