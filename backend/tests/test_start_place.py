"""출발지 지정("강남역에서 출발") 파싱·동선 반영."""
from app.adapters.map_service import MockMapService
from app.pipeline.agent import generate_course
from app.pipeline.decomposition import parse_constraints
from app.pipeline.planner import route_order_from
from app.schemas import Place


def test_출발지를_파싱한다():
    c = parse_constraints("강남역에서 출발해서 저녁에 3시간")
    assert c.start_place == "강남역"


def test_출발지만_말해도_지역으로_쓴다():
    c = parse_constraints("서울숲에서 모여서 놀자")
    assert c.region == "서울숲"


def test_출발지_없으면_None():
    assert parse_constraints("성수동 카페 추천").start_place is None


def _place(pid: str, lat: float, lng: float) -> Place:
    return Place(id=pid, name=pid, lat=lat, lng=lng)


def test_출발지에서_가장_가까운_곳이_먼저다():
    origin = _place("origin", 37.500, 127.000)
    far = _place("far", 37.520, 127.020)
    near = _place("near", 37.501, 127.001)
    assert route_order_from([far, near], origin)[0].id == "near"


async def test_출발지가_있어도_코스가_생성된다():
    result = await generate_course("강남역에서 출발해서 저녁 코스", MockMapService())
    assert result.timeline
