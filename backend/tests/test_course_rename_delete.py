from fastapi.testclient import TestClient

from app.main import app
from tests.helpers import owned_course

client = TestClient(app)


def _course(owner: str | None = None) -> str:
    return owned_course(client, owner)[1]


def test_이름을_변경한다():
    uid, cid = owned_course(client)
    res = client.patch(f"/courses/{cid}", json={"title": "성수 데이트"}, headers={"X-User-Id": uid})
    assert res.status_code == 200
    assert res.json()["title"] == "성수 데이트"
    assert client.get(f"/courses/{cid}").json()["title"] == "성수 데이트"


def test_빈_이름은_거부된다():
    uid, cid = owned_course(client)
    assert client.patch(f"/courses/{cid}", json={"title": ""}, headers={"X-User-Id": uid}).status_code == 422


def test_생성자가_아니면_변경_삭제_불가():
    uid = client.post("/signup", json={"phone": "010-1111-2222"}).json()["user_id"]
    cid = _course(uid)
    assert client.patch(f"/courses/{cid}", json={"title": "x"}).status_code == 403
    assert client.delete(f"/courses/{cid}").status_code == 403
    assert client.patch(
        f"/courses/{cid}", json={"title": "내 코스"}, headers={"X-User-Id": uid}
    ).status_code == 200


def test_삭제하면_조회되지_않는다():
    uid, cid = owned_course(client)
    assert client.delete(f"/courses/{cid}", headers={"X-User-Id": uid}).json() == {"ok": True}
    assert client.get(f"/courses/{cid}").status_code == 404


def test_없는_코스는_404():
    assert client.patch("/courses/nope", json={"title": "x"}).status_code == 404
    assert client.delete("/courses/nope").status_code == 404


def test_내_코스는_최근_순으로_나온다():
    uid = client.post("/signup", json={"phone": "010-3333-4444"}).json()["user_id"]
    first = _course(uid)
    second = _course(uid)
    ids = [c["id"] for c in client.get(f"/users/{uid}/courses", headers={"X-User-Id": uid}).json()]
    assert ids.index(second) < ids.index(first)


def test_내_코스는_상한만큼만_돌려준다():
    from app.store import CourseStore

    store = CourseStore()
    for _ in range(5):
        store.create(owner_id="u-limit")
    assert len(store.list_by_owner("u-limit", limit=3)) == 3
    assert len(store.list_by_owner("u-limit")) == 5
