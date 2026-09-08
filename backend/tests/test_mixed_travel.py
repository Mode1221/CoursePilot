"""먼 도보 구간의 대중교통 자동 전환(이동수단 혼합)."""
from app.adapters.map_service import MockMapService
from app.pipeline.decomposition import parse_constraints
from app.pipeline.validation import build_timeline
from app.schemas import Place, PlanConstraints, TravelMode


def _place(pid: str, lat: float) -> Place:
    return Place(id=pid, name=pid, lat=lat, lng=127.0)


def _constraints(**kw) -> PlanConstraints:
    return PlanConstraints(travel_mode=TravelMode.WALK, **kw)


async def test_먼_구간은_대중교통으로_바뀐다():
    places = [_place("a", 37.50), _place("b", 37.55)]  # 도보로 한참 걸리는 거리
    timeline = await build_timeline(places, _constraints(), MockMapService())
    assert len(timeline) == 2
    assert timeline[0].travel_to_next.mode is TravelMode.TRANSIT


async def test_가까우면_도보를_유지한다():
    places = [_place("a", 37.500), _place("b", 37.501)]
    timeline = await build_timeline(places, _constraints(), MockMapService())
    assert timeline[0].travel_to_next.mode is TravelMode.WALK


async def test_도보로만_요청하면_바꾸지_않는다():
    places = [_place("a", 37.50), _place("b", 37.55)]
    c = _constraints(strict_travel_mode=True)
    timeline = await build_timeline(places, c, MockMapService())
    assert timeline[0].travel_to_next.mode is TravelMode.WALK


def test_도보로만_표현을_파싱한다():
    assert parse_constraints("도보로만 이동하고 싶어").strict_travel_mode is True
    assert parse_constraints("도보 15분 이내").strict_travel_mode is False


async def test_재계산도_먼_구간은_대중교통으로_바꾼다():
    from datetime import time

    from app.pipeline.validation import recompute

    places = [_place("a", 37.50), _place("b", 37.55)]
    timeline = await recompute(places, time(12, 0), TravelMode.WALK, MockMapService())
    assert timeline[0].travel_to_next.mode is TravelMode.TRANSIT
