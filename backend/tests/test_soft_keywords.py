from app.pipeline.agent import MAX_QUERY_KEYWORDS, _attempt
from app.pipeline.decomposition import parse_constraints
from app.schemas import Place, PlanConstraints, Route, TravelMode
from app.adapters.map_service import MapService


def test_실사용_표현을_키워드로_잡는다():
    assert "실내" in parse_constraints("비 오는 날 실내 데이트").keywords
    assert set(parse_constraints("전시 보고 디저트").keywords) == {"전시", "디저트"}
    assert "와인" in parse_constraints("와인 한잔 하고 싶어").keywords


class _RecordingMapService(MapService):
    """검색 질의에 실제로 전달된 키워드를 기록한다."""

    def __init__(self) -> None:
        self.received: list[str] = []

    async def search_places(self, region: str, keywords: list[str], limit: int = 10) -> list[Place]:
        self.received = list(keywords)
        return []

    async def get_route(self, origin: Place, dest: Place, mode: TravelMode) -> Route:
        return Route(
            from_place_id=origin.id, to_place_id=dest.id, mode=mode, duration_min=5, distance_m=100
        )


async def test_검색_질의_키워드는_상한을_넘지_않는다():
    svc = _RecordingMapService()
    constraints = PlanConstraints(region="성수동", keywords=["실내", "전시", "디저트", "사진", "카페"])
    await _attempt(constraints, svc)
    assert svc.received == constraints.keywords[:MAX_QUERY_KEYWORDS]
