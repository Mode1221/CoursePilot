from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _course(owner: str | None = None) -> str:
    headers = {"X-User-Id": owner} if owner else {}
    return client.post("/courses", headers=headers).json()["id"]


def test_이름을_변경한다():
    cid = _course()
    res = client.patch(f"/courses/{cid}", json={"title": "성수 데이트"})
    assert res.status_code == 200
    assert res.json()["title"] == "성수 데이트"
    assert client.get(f"/courses/{cid}").json()["title"] == "성수 데이트"


def test_빈_이름은_거부된다():
    cid = _course()
    assert client.patch(f"/courses/{cid}", json={"title": ""}).status_code == 422


def test_생성자가_아니면_변경_삭제_불가():
    uid = client.post("/signup", json={"phone": "010-1111-2222"}).json()["user_id"]
    cid = _course(uid)
    assert client.patch(f"/courses/{cid}", json={"title": "x"}).status_code == 403
    assert client.delete(f"/courses/{cid}").status_code == 403
    assert client.patch(
        f"/courses/{cid}", json={"title": "내 코스"}, headers={"X-User-Id": uid}
    ).status_code == 200


def test_삭제하면_조회되지_않는다():
    cid = _course()
    assert client.delete(f"/courses/{cid}").json() == {"ok": True}
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
