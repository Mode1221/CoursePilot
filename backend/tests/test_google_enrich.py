"""Google 평점 보강: 평점 없는 장소만 조회한다."""
from app.adapters.google import GooglePlacesEnricher
from app.metrics import metrics_store
from app.schemas import Place


def _place(pid: str, rating: float | None) -> Place:
    return Place(id=pid, name=pid, lat=37.5, lng=127.0, rating=rating)


class _FakeEnricher(GooglePlacesEnricher):
    def __init__(self) -> None:
        self._key = "test-key"
        self.queried: list[str] = []

    async def _rating_for(self, place: Place):
        self.queried.append(place.id)
        return 4.2, 100


async def test_평점_있는_장소는_조회하지_않는다():
    metrics_store.clear()
    enricher = _FakeEnricher()
    places = [_place("has", 4.9), _place("none", None)]
    result = await enricher.enrich(places)
    assert enricher.queried == ["none"]
    assert result[0].rating == 4.9
    assert result[1].rating == 4.2


async def test_전부_평점이_있으면_호출하지_않는다():
    enricher = _FakeEnricher()
    await enricher.enrich([_place("a", 4.0)])
    assert enricher.queried == []


def test_enricher_는_싱글턴이다():
    from app.adapters.google import get_places_enricher

    assert get_places_enricher() is get_places_enricher()
