"""코스 복제 엔드포인트."""
from fastapi.testclient import TestClient

from app.main import app
from tests.helpers import member, owned_course

client = TestClient(app)


def test_사본은_요청자_소유의_새_코스다():
    u1, original = owned_course(client)
    u2 = member(client)
    client.patch("/courses/" + original, json={"title": "성수 코스"}, headers={"X-User-Id": u1})

    copy = client.post(f"/courses/{original}/duplicate", headers={"X-User-Id": u2}).json()
    assert copy["id"] != original
    assert copy["owner_id"] == u2
    assert copy["title"] == "성수 코스 (사본)"


def test_원본은_그대로다():
    u1, original = owned_course(client)
    client.post(f"/courses/{original}/duplicate", headers={"X-User-Id": member(client)})
    same = client.get(f"/courses/{original}").json()
    assert same["owner_id"] == u1
    assert same["title"] == "새 코스"


def test_신원_없이는_복제할_수_없다():
    _, original = owned_course(client)
    res = client.post(f"/courses/{original}/duplicate")
    assert res.status_code == 401
    assert res.json()["code"] == "guest_required"


def test_없는_코스는_404():
    assert client.post("/courses/nope/duplicate").status_code == 404
