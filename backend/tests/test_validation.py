from datetime import time

import pytest

from app.adapters.map_service import MapService
from app.pipeline.validation import build_timeline, stay_minutes
from app.schemas import Place, PlanConstraints, Route, TravelMode


class FixedRouteService(MapService):
    """모든 구간을 10분으로 고정 → 시각 계산을 결정론적으로 검증."""

    async def search_places(self, region, keywords, limit=10):
        return []

    async def get_route(self, origin, dest, mode):
        return Route(from_place_id=origin.id, to_place_id=dest.id, mode=mode,
                     duration_min=10, distance_m=100)


def _p(pid, open_t=None, close_t=None, bs=None, be=None, price=None, category=None):
    return Place(id=pid, name=pid, lat=37.5, lng=127.0, price=price, category=category,
                 open_time=open_t, close_time=close_t, break_start=bs, break_end=be)


def test_stay_minutes_by_category():
    assert stay_minutes(_p("a", category="restaurant")) == 90
    assert stay_minutes(_p("b", category="술집")) == 120
    assert stay_minutes(_p("c", category="cafe")) == 60


@pytest.mark.asyncio
async def test_budget_hard_constraint_drops_expensive():
    # 예산 3만원: 2만+2만 이면 두 번째에서 누적 4만 초과 → 폐기
    places = [_p("A", price=20_000), _p("B", price=20_000), _p("C", price=5_000)]
    c = PlanConstraints(start_time=time(12, 0), budget_max=30_000)
    tl = await build_timeline(places, c, FixedRouteService())
    ids = [it.place.id for it in tl]
    assert "A" in ids and "B" not in ids and "C" in ids  # 2만+5천=2.5만 ≤ 3만


@pytest.mark.asyncio
async def test_departure_past_close_is_dropped():
    # 21:30 도착, 카페 체류 60분 → 22:30 출발이 22:00 폐점을 넘김 → 폐기
    late = _p("late", open_t=time(10, 0), close_t=time(22, 0), category="cafe")
    ok = _p("ok", open_t=time(0, 0), close_t=time(23, 59), category="cafe")
    c = PlanConstraints(start_time=time(21, 30))
    tl = await build_timeline([late, ok], c, FixedRouteService())
    assert [it.place.id for it in tl] == ["ok"]  # late 는 폐점 초과로 제외


@pytest.mark.asyncio
async def test_stay_crossing_break_is_dropped():
    # 14:30 도착, 60분 체류 → 15:00 브레이크 진입 → 폐기
    p = _p("b", open_t=time(10, 0), close_t=time(22, 0), bs=time(15, 0), be=time(17, 0), category="cafe")
    ok = _p("ok", open_t=time(0, 0), close_t=time(23, 59), category="cafe")
    c = PlanConstraints(start_time=time(14, 30))
    tl = await build_timeline([p, ok], c, FixedRouteService())
    assert [it.place.id for it in tl] == ["ok"]


@pytest.mark.asyncio
async def test_skipped_place_does_not_drift_cursor():
    # A(13:00) → B는 13:00~14:00 브레이크라 스킵 → C 도착은 A출발+10분=14:10 이어야 함
    places = [
        _p("A"),
        _p("B", bs=time(0, 0), be=time(23, 59)),  # 항상 브레이크 → 스킵
        _p("C"),
    ]
    c = PlanConstraints(start_time=time(13, 0), travel_mode=TravelMode.WALK)
    tl = await build_timeline(places, c, FixedRouteService())

    assert [it.place.id for it in tl] == ["A", "C"]
    assert tl[0].arrive == time(13, 0)
    # A 체류 60분 → 14:00, 이동 10분 → C 도착 14:10 (스킵된 B의 이동으로 밀리지 않음)
    assert tl[1].arrive == time(14, 10)
