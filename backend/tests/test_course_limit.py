from fastapi.testclient import TestClient

from app.main import MAX_COURSE_ITEMS, app
from app.places import place_repo
from app.schemas import Place

client = TestClient(app)


def test_상한을_넘으면_추가할_수_없다():
    cid = client.post("/courses").json()["id"]
    places = [
        Place(id=f"lim-{i}", name=f"장소{i}", lat=37.54 + i * 0.001, lng=127.05)
        for i in range(MAX_COURSE_ITEMS + 1)
    ]
    place_repo.upsert_many(places)

    ids = [p.id for p in places[:MAX_COURSE_ITEMS]]
    assert client.post(f"/courses/{cid}/items", json={"place_ids": ids}).status_code == 200

    res = client.post(f"/courses/{cid}/places", json={"place_id": places[-1].id})
    assert res.status_code == 409
    assert str(MAX_COURSE_ITEMS) in res.json()["detail"]


def test_상한을_넘는_구성은_422():
    cid = client.post("/courses").json()["id"]
    ids = [f"x-{i}" for i in range(MAX_COURSE_ITEMS + 1)]
    assert client.post(f"/courses/{cid}/items", json={"place_ids": ids}).status_code == 422
