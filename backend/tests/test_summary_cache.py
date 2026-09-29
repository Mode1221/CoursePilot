"""리뷰 요약 캐시."""
from fastapi.testclient import TestClient

from app.main import _summary_cache, app

client = TestClient(app)


def _body(place_id: str = "p1") -> dict:
    # 요약은 서버가 가진 장소 이름으로만 만든다 — 저장된 장소여야 한다
    from app.places import place_repo
    from app.schemas import Place

    place_repo.upsert_many([Place(id=place_id, name="성수 카페", lat=37.54, lng=127.05)])
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
