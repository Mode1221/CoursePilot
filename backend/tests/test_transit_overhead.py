"""대중교통 근사에 대기·환승 고정 비용 반영."""
from app.adapters.map_service import MockMapService
from app.adapters.naver import _straight_line_route
from app.constants import TRANSIT_OVERHEAD_MIN
from app.schemas import Place, TravelMode


def _place(pid: str, lat: float) -> Place:
    return Place(id=pid, name=pid, lat=lat, lng=127.0)


def test_직선근사에_고정비용이_더해진다():
    a, b = _place("a", 37.500), _place("b", 37.505)
    transit = _straight_line_route(a, b, TravelMode.TRANSIT)
    assert transit.duration_min >= TRANSIT_OVERHEAD_MIN


def test_가까운_거리는_도보가_더_빠르다():
    a, b = _place("a", 37.500), _place("b", 37.502)
    walk = _straight_line_route(a, b, TravelMode.WALK)
    transit = _straight_line_route(a, b, TravelMode.TRANSIT)
    assert walk.duration_min < transit.duration_min


async def test_mock도_같은_규칙을_쓴다():
    svc = MockMapService()
    a, b = _place("a", 37.500), _place("b", 37.502)
    walk = await svc.get_route(a, b, TravelMode.WALK)
    transit = await svc.get_route(a, b, TravelMode.TRANSIT)
    assert walk.duration_min < transit.duration_min
