"""물리적 제약 검증 (7-3) 및 타임라인 계산."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from app.adapters.map_service import MapService
from app.schemas import Place, PlanConstraints, Route, TimelineItem, TravelMode


def _overlaps_break(t: time, place: Place) -> bool:
    """방문 시각이 브레이크 타임에 걸리는지."""
    if place.break_start and place.break_end:
        return place.break_start <= t < place.break_end
    return False


def is_open_at(place: Place, t: time) -> bool:
    """해당 시각에 영업 중인지 (영업시간 + 브레이크 타임 반영)."""
    if place.open_time and t < place.open_time:
        return False
    if place.close_time and t >= place.close_time:
        return False
    return not _overlaps_break(t, place)


async def build_timeline(
    places: list[Place],
    constraints: PlanConstraints,
    map_service: MapService,
) -> list[TimelineItem]:
    """후보 장소를 순서대로 배치하며 이동시간/영업시간을 검증한 타임라인 생성.

    조건 위반 장소는 폐기(스킵)한다.
    """
    mode = constraints.travel_mode
    stay_min = 60  # 장소당 기본 체류시간
    cursor = _as_datetime(constraints.start_time or time(12, 0))
    end_dt = _as_datetime(constraints.end_time) if constraints.end_time else None

    timeline: list[TimelineItem] = []
    prev: Place | None = None

    for place in places:
        # 이전 장소로부터 이동
        route: Route | None = None
        if prev is not None:
            route = await map_service.get_route(prev, place, mode)
            if (
                constraints.max_travel_min is not None
                and route.duration_min > constraints.max_travel_min
            ):
                continue  # 이동시간 조건 위반 → 폐기
            cursor = cursor + timedelta(minutes=route.duration_min)

        arrive = cursor.time()
        if not is_open_at(place, arrive):
            continue  # 영업시간/브레이크 위반 → 폐기

        depart_dt = cursor + timedelta(minutes=stay_min)
        if end_dt is not None and depart_dt > end_dt:
            break  # 전체 시간 초과 → 종료

        if timeline and route is not None:
            timeline[-1].travel_to_next = route

        timeline.append(
            TimelineItem(place=place, arrive=arrive, depart=depart_dt.time())
        )
        cursor = depart_dt
        prev = place

    return timeline


async def recompute(
    places: list[Place],
    start_time: time,
    mode: TravelMode,
    map_service: MapService,
    stay_min: int = 60,
) -> list[TimelineItem]:
    """주어진 장소 순서를 그대로 유지하며 도착/출발/이동만 재계산한다(드롭 없음).

    수동 편집·부분 교체 후 동기화용 (4-3).
    """
    cursor = _as_datetime(start_time)
    timeline: list[TimelineItem] = []
    prev: Place | None = None

    for place in places:
        route: Route | None = None
        if prev is not None:
            route = await map_service.get_route(prev, place, mode)
            cursor = cursor + timedelta(minutes=route.duration_min)
            timeline[-1].travel_to_next = route

        arrive = cursor.time()
        depart_dt = cursor + timedelta(minutes=stay_min)
        timeline.append(TimelineItem(place=place, arrive=arrive, depart=depart_dt.time()))
        cursor = depart_dt
        prev = place

    return timeline


def _as_datetime(t: time) -> datetime:
    return datetime.combine(date.today(), t)
