from fastapi.testclient import TestClient

from app.cooccurrence import CooccurrenceStore
from app.main import api
from app.places import PlaceRepository
from app.schemas import Place


def _p(pid):
    return Place(id=pid, name=f"n-{pid}", category="카페", lat=37.5, lng=127.0, rating=4.0)


def test_place_repo_roundtrip():
    repo = PlaceRepository()
    repo.upsert_many([_p("a"), _p("b")])
    got = repo.get_many(["a", "b", "z"])
    assert set(got) == {"a", "b"}
    assert got["a"].name == "n-a"


def test_top_partners_ranking():
    cs = CooccurrenceStore()
    cs.bump_course(["a", "b"])
    cs.bump_course(["a", "b"])
    cs.bump_course(["a", "c"])
    top = cs.top_partners("a", 5)
    assert top[0] == ("b", 2.0)
    assert ("c", 1.0) in top


def test_related_endpoint_empty_when_no_data():
    client = TestClient(api)
    res = client.get("/places/unknown-place/related")
    assert res.status_code == 200
    assert res.json() == []
