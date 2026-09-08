import pytest

from app.adapters.map_service import MockMapService, SafeMapService
from app.adapters.naver import _haversine_m, _katech_to_wgs84, _strip_tags


def test_strip_tags():
    assert _strip_tags("<b>성수</b> 카페") == "성수 카페"


def test_katech_conversion():
    lat, lng = _katech_to_wgs84("1270557000", "375445000")
    assert round(lng, 4) == 127.0557
    assert round(lat, 4) == 37.5445


def test_haversine_zero():
    assert _haversine_m(37.5, 127.0, 37.5, 127.0) == 0


class _Boom(MockMapService):
    async def search_places(self, *a, **k):
        raise RuntimeError("api down")


@pytest.mark.asyncio
async def test_safe_fallback_on_error():
    svc = SafeMapService(_Boom(), MockMapService())
    places = await svc.search_places("성수동", [], 3)
    assert len(places) == 3  # 폴백 동작


def test_single_query_when_limit_small():
    from app.adapters.naver import _build_queries

    assert _build_queries("성수동", ["조용한"], 5) == ["성수동 조용한"]


def test_multiple_queries_when_limit_large():
    from app.adapters.naver import _build_queries

    queries = _build_queries("성수동", [], 24)
    assert queries[0] == "성수동"
    assert len(queries) == 5  # 5개씩 24개를 채우려면 총 5회
    assert all(q.startswith("성수동") for q in queries)
