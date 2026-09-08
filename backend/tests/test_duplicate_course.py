"""코스 복제 엔드포인트."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _course_with_place(owner: str) -> str:
    cid = client.post("/courses", headers={"X-User-Id": owner}).json()["id"]
    return cid


def test_사본은_요청자_소유의_새_코스다():
    original = _course_with_place("u1")
    client.patch("/courses/" + original, json={"title": "성수 코스"}, headers={"X-User-Id": "u1"})

    copy = client.post(f"/courses/{original}/duplicate", headers={"X-User-Id": "u2"}).json()
    assert copy["id"] != original
    assert copy["owner_id"] == "u2"
    assert copy["title"] == "성수 코스 (사본)"


def test_원본은_그대로다():
    original = _course_with_place("u1")
    client.post(f"/courses/{original}/duplicate", headers={"X-User-Id": "u2"})
    same = client.get(f"/courses/{original}").json()
    assert same["owner_id"] == "u1"
    assert same["title"] == "새 코스"


def test_없는_코스는_404():
    assert client.post("/courses/nope/duplicate").status_code == 404
