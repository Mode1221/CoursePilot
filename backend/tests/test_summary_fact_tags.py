"""리뷰 요약에 저장된 사실 태그를 함께 노출한다."""
from fastapi.testclient import TestClient

from app.main import api
from app.places import place_repo
from app.schemas import Place

client = TestClient(api)


def _store(**kw):
    place_repo._mem.clear()
    place_repo.upsert_many(
        [Place(**{"id": "p1", "name": "성수커피", "lat": 37.5, "lng": 127.0, **kw})]
    )



def _summary(place_id="p1"):
    return client.post(
        "/reviews/summary", json={"place_id": place_id, "place_name": "성수커피"}
    ).json()


def test_저장된_사실_태그가_함께_나온다():
    _store(id="tag-1", fact_tags=["단체석"], caution_tags=["반려동물"])
    body = _summary("tag-1")
    assert "단체석" in body["pros"] and "반려동물" in body["cons"]
    place_repo._mem.clear()


def test_주의_축은_좋은_점에서_뺀다():
    _store(id="tag-2", fact_tags=["웨이팅"], caution_tags=["웨이팅"])
    body = _summary("tag-2")
    assert "웨이팅" in body["cons"] and "웨이팅" not in body["pros"]
    place_repo._mem.clear()


def test_저장된_장소가_없으면_리뷰_축만_나온다():
    place_repo._mem.clear()
    body = _summary("unknown")
    assert isinstance(body["pros"], list) and isinstance(body["cons"], list)
