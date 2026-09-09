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


def test_detour_factor_applied_to_walking():
    from app.adapters.naver import DETOUR_FACTOR, _haversine_m, _straight_line_route
    from app.schemas import Place, TravelMode

    a = Place(id="a", name="A", lat=37.5400, lng=127.0550)
    b = Place(id="b", name="B", lat=37.5450, lng=127.0600)
    straight = _haversine_m(a.lat, a.lng, b.lat, b.lng)
    route = _straight_line_route(a, b, TravelMode.WALK)
    assert route.distance_m == round(straight * DETOUR_FACTOR)


def test_좌표를_못_믿는_장소는_제외한다():
    from app.adapters.naver import _katech_to_wgs84

    assert _katech_to_wgs84("1270000000", "375000000") == (37.5, 127.0)
    assert _katech_to_wgs84(None, None) is None
    assert _katech_to_wgs84("abc", "def") is None
    assert _katech_to_wgs84("0", "0") is None  # 적도 앞바다
    assert _katech_to_wgs84("1390000000", "355000000") is None  # 한국 밖


async def test_좌표_불량_항목은_결과에서_빠진다(monkeypatch):
    from app.adapters.naver import NaverMapService

    payload = {
        "items": [
            {"title": "좋은 곳", "mapx": "1270000000", "mapy": "375000000", "address": "서울"},
            {"title": "이상한 곳", "mapx": "0", "mapy": "0", "address": "??"},
        ]
    }

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return payload

    svc = NaverMapService()

    async def _get(url, params=None, headers=None):
        return _Resp()

    monkeypatch.setattr(svc._client, "get", _get)
    places = await svc.search_places("성수동", [], limit=5)
    assert [p.name for p in places] == ["좋은 곳"]
