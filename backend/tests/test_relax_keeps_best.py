"""조건 완화가 원래 결과보다 나빠지면 원래 결과를 유지한다."""
from app.adapters.map_service import MapService, MockMapService
from app.pipeline.agent import generate_course
from app.schemas import Place, Route, TravelMode


class ShrinkingMapService(MapService):
    """호출할수록 후보가 줄어드는 서비스(완화 재시도가 더 나쁜 상황 재현)."""

    def __init__(self) -> None:
        self._calls = 0
        self._mock = MockMapService()

    async def search_places(self, region, keywords, limit=10):
        self._calls += 1
        places = await self._mock.search_places(region, keywords, limit=limit)
        return places if self._calls == 1 else places[:1]

    async def get_route(self, origin: Place, dest: Place, mode: TravelMode) -> Route:
        return await self._mock.get_route(origin, dest, mode)


async def test_완화가_더_나쁘면_원래_결과를_쓴다():
    svc = ShrinkingMapService()
    result = await generate_course("성수동에서 놀자", svc, force_relax=True)
    assert len(result.timeline) > 1
