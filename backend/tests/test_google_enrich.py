import pytest

from app.adapters.google import GooglePlacesEnricher
from app.adapters.map_service import EnrichedMapService, MockMapService
from app.schemas import Place


def _p(pid, rating=None):
    return Place(id=pid, name=pid, category="카페", lat=37.5, lng=127.0, rating=rating)


@pytest.mark.asyncio
async def test_enricher_noop_without_key(monkeypatch):
    e = GooglePlacesEnricher()
    monkeypatch.setattr(e, "_key", "")  # 키 없음
    places = [_p("a"), _p("b")]
    out = await e.enrich(places)
    assert [p.rating for p in out] == [None, None]  # 무영향


@pytest.mark.asyncio
async def test_enricher_fills_only_missing_rating(monkeypatch):
    e = GooglePlacesEnricher()
    monkeypatch.setattr(e, "_key", "test-key")

    async def fake_rating(place):
        return (4.7, 120)

    monkeypatch.setattr(e, "_rating_for", fake_rating)
    places = [_p("a"), _p("b", rating=3.0)]
    out = await e.enrich(places)
    assert out[0].rating == 4.7   # 없던 평점 보강
    assert out[1].rating == 3.0   # 기존 평점 유지


@pytest.mark.asyncio
async def test_enriched_map_service_delegates_search():
    # 키 없으면 enricher 가 무영향이라 Mock 결과 그대로
    svc = EnrichedMapService(MockMapService())
    places = await svc.search_places("성수동", [], limit=3)
    assert len(places) == 3
