"""장소 검색 결과 TTL 캐시."""
from app.adapters.map_service import CachedSearchMapService, MockMapService
from app.schemas import Place, Route, TravelMode


class _Counting(MockMapService):
    def __init__(self) -> None:
        self.calls = 0

    async def search_places(self, region, keywords, limit=10):
        self.calls += 1
        return await super().search_places(region, keywords, limit)


async def test_같은_조건은_다시_호출하지_않는다():
    inner = _Counting()
    svc = CachedSearchMapService(inner)
    first = await svc.search_places("성수동", ["카페"], 5)
    second = await svc.search_places("성수동", ["카페"], 5)
    assert inner.calls == 1
    assert [p.id for p in first] == [p.id for p in second]


async def test_조건이_다르면_다시_호출한다():
    inner = _Counting()
    svc = CachedSearchMapService(inner)
    await svc.search_places("성수동", ["카페"], 5)
    await svc.search_places("홍대", ["카페"], 5)
    await svc.search_places("성수동", ["술집"], 5)
    assert inner.calls == 3


async def test_TTL_이_지나면_다시_호출한다():
    inner = _Counting()
    svc = CachedSearchMapService(inner, ttl_sec=0)
    await svc.search_places("성수동", [], 5)
    await svc.search_places("성수동", [], 5)
    assert inner.calls == 2


async def test_경로는_위임한다():
    svc = CachedSearchMapService(MockMapService())
    a = Place(id="a", name="a", lat=37.5, lng=127.0)
    b = Place(id="b", name="b", lat=37.51, lng=127.0)
    route = await svc.get_route(a, b, TravelMode.WALK)
    assert isinstance(route, Route)
