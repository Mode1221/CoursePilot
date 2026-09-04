from datetime import time

import pytest

from app.adapters.map_service import MapService
from app.pipeline.validation import build_timeline
from app.schemas import Place, PlanConstraints, Route, TravelMode


class FixedRouteService(MapService):
    """모든 구간을 10분으로 고정 → 시각 계산을 결정론적으로 검증."""

    async def search_places(self, region, keywords, limit=10):
        return []

    async def get_route(self, origin, dest, mode):
        return Route(from_place_id=origin.id, to_place_id=dest.id, mode=mode,
                     duration_min=10, distance_m=100)


def _p(pid, open_t=None, close_t=None, bs=None, be=None):
    return Place(id=pid, name=pid, lat=37.5, lng=127.0,
                 open_time=open_t, close_time=close_t, break_start=bs, break_end=be)


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
