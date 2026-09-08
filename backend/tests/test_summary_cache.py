"""리뷰 요약 캐시."""
from fastapi.testclient import TestClient

from app.main import _summary_cache, app

client = TestClient(app)


def _body(place_id: str = "p1") -> dict:
    return {"place_id": place_id, "place_name": "성수 카페"}


def test_같은_장소는_캐시된_결과를_준다():
    _summary_cache.clear()
    first = client.post("/reviews/summary", json=_body()).json()
    second = client.post("/reviews/summary", json=_body()).json()
    assert first == second
    assert len(_summary_cache) == 1


def test_다른_장소는_따로_캐시된다():
    _summary_cache.clear()
    client.post("/reviews/summary", json=_body("p1"))
    client.post("/reviews/summary", json=_body("p2"))
    assert len(_summary_cache) == 2
