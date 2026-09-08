"""개인 데이터는 본인만 접근 가능."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _signup() -> str:
    return client.post("/signup", json={"phone": "01012340000"}).json()["user_id"]


def test_남의_코스_목록은_못_본다():
    uid = _signup()
    assert client.get(f"/users/{uid}/courses", headers={"X-User-Id": "other"}).status_code == 403
    assert client.get(f"/users/{uid}/courses").status_code == 403


def test_본인은_볼_수_있다():
    uid = _signup()
    res = client.get(f"/users/{uid}/courses", headers={"X-User-Id": uid})
    assert res.status_code == 200


def test_남의_크레딧_조회_충전은_막는다():
    uid = _signup()
    assert client.get(f"/users/{uid}/credits", headers={"X-User-Id": "other"}).status_code == 403
    res = client.post(
        f"/users/{uid}/purchase", json={"points": 5}, headers={"X-User-Id": "other"}
    )
    assert res.status_code == 403


def test_남의_북마크는_건드릴_수_없다():
    uid = _signup()
    headers = {"X-User-Id": "other"}
    assert client.get(f"/users/{uid}/bookmarks", headers=headers).status_code == 403
    assert client.put(f"/users/{uid}/bookmarks/c1", headers=headers).status_code == 403
    assert client.delete(f"/users/{uid}/bookmarks/c1", headers=headers).status_code == 403
