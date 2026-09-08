"""AI 명령은 코스 생성자만 실행할 수 있다."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _course(owner: str) -> str:
    return client.post("/courses", headers={"X-User-Id": owner}).json()["id"]


def test_다른_사용자는_생성을_못한다():
    cid = _course("owner1")
    res = client.post(
        f"/courses/{cid}/generate", json={"text": "성수동"}, headers={"X-User-Id": "other"}
    )
    assert res.status_code == 403


def test_다른_사용자는_완화도_못한다():
    cid = _course("owner1")
    res = client.post(f"/courses/{cid}/relax", headers={"X-User-Id": "other"})
    assert res.status_code == 403


def test_비로그인은_여전히_403():
    cid = _course("owner1")
    assert client.post(f"/courses/{cid}/generate", json={"text": "성수동"}).status_code == 403


def test_없는_코스는_404():
    res = client.post(
        "/courses/nope/generate", json={"text": "성수동"}, headers={"X-User-Id": "u1"}
    )
    assert res.status_code == 404
