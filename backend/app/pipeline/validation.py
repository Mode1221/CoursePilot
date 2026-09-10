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


LARGE_PARTY = 5  # 이 인원부터 주문·자리 잡기에 시간이 더 걸린다
LARGE_PARTY_EXTRA_MIN = 20


def stay_minutes(place: Place, party_size: int | None = None) -> int:
    """카테고리별 기본 체류시간. 식당은 길게, 카페/전시는 보통.

    대인원은 주문·계산에 시간이 더 걸리므로 여유를 더한다.
    """
    cat = (place.category or "").lower()
    if any(
        k in cat
        for k in ("restaurant", "식당", "음식", "고기", "한식", "일식", "중식", "양식", "뷔페")
    ):
        base = 90
    elif any(k in cat for k in ("bar", "술집", "펍", "포차", "주점", "호프", "이자카야", "포장마차")):
        base = 120
    elif any(k in cat for k in ("영화", "cinema", "공연", "뮤지컬", "콘서트")):
        base = 150  # 상영·공연 시간 자체가 길다
    elif any(k in cat for k in ("전시", "갤러리", "미술", "박물", "체험", "방탈출", "볼링")):
        base = 90  # 관람·체험은 카페보다 오래 머문다
    else:
        base = 60  # 카페·기타
    if party_size is not None and party_size >= LARGE_PARTY:
        base += LARGE_PARTY_EXTRA_MIN
    return base


# 추정가로 예산을 볼 때 허용하는 여유폭(카테고리 평균의 오차 흡수).
ESTIMATE_SLACK = 1.2


def _budget_limit(budget_max: int, place: Place) -> float:
    """이 장소를 판단할 때 적용할 예산 상한."""
    return budget_max * ESTIMATE_SLACK if place.price_estimated else budget_max


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


# 도보가 이 시간을 넘으면 그 구간만 대중교통으로 갈아탄다(수단 혼합).
WALK_SWITCH_MIN = 20


async def best_route(
    prev: Place,
    place: Place,
    mode: TravelMode,
    map_service: MapService,
    strict: bool = False,
) -> Route:
    """기본 수단으로 경로를 구하되, 너무 먼 도보 구간은 대중교통으로 대체한다."""
    route = await map_service.get_route(prev, place, mode)
    if mode is not TravelMode.WALK or strict or route.duration_min <= WALK_SWITCH_MIN:
        return route
    alt = await map_service.get_route(prev, place, TravelMode.TRANSIT)
    return alt if alt.duration_min < route.duration_min else route


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
    if end_dt is not None and end_dt <= cursor:
        end_dt += timedelta(days=1)  # 자정을 넘기는 코스(예: 22시~1시)
    elif end_dt is None and constraints.duration_min:
        # 시작 시각을 말하지 않고 "2시간"만 말한 경우에도 그 시간은 지켜야 한다.
        # (예전엔 종료 시각이 없다는 이유로 소요 시간을 통째로 무시했다)
        end_dt = cursor + timedelta(minutes=constraints.duration_min)

    timeline: list[TimelineItem] = []
    prev: Place | None = None
    spent = 0  # 누적 예상 비용(예산 하드 제약)

    for place in places:
        # 예산 하드 제약: 누적 비용이 상한을 넘으면 폐기 (가격 미상 장소는 통과).
        # 추정가는 카테고리 평균일 뿐이라 그대로 자르면 멀쩡한 가게가 떨어진다 →
        # 추정가로 판단할 때만 여유폭을 준다. 실제 가격은 종전대로 엄격히 본다.
        if (
            constraints.budget_max is not None
            and place.price is not None
            and spent + place.price > _budget_limit(constraints.budget_max, place)
        ):
            continue

        # 이전 장소로부터 이동. 아직 cursor 는 진전시키지 않는다(스킵 시 드리프트 방지).
        route: Route | None = None
        arrive_dt = cursor
        if prev is not None:
            route = await best_route(
                prev, place, mode, map_service, constraints.strict_travel_mode
            )
            if (
                constraints.max_travel_min is not None
                and route.duration_min > constraints.max_travel_min
            ):
                continue  # 이동시간 조건 위반 → 폐기 (cursor 유지)
            arrive_dt = cursor + timedelta(minutes=route.duration_min)

        arrive = arrive_dt.time()
        depart_dt = arrive_dt + timedelta(minutes=stay_minutes(place, constraints.party_size))
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
    strict_mode: bool = False,
) -> list[TimelineItem]:
    """주어진 장소 순서를 그대로 유지하며 도착/출발/이동만 재계산한다(드롭 없음).

    수동 편집·부분 교체 후 동기화용 (4-3). 체류시간은 카테고리별로 계산.
    """
    # 구간 순서는 고정이고 각 경로 계산은 서로 독립 → 병렬 조회 후 순차 배치
    routes: list[Route] = []
    if len(places) > 1:
        routes = await asyncio.gather(
            *(
                best_route(places[i], places[i + 1], mode, map_service, strict_mode)
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
