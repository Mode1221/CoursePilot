from fastapi.testclient import TestClient

from app.main import app
from app.pipeline.decomposition import parse_constraints

client = TestClient(app)


def test_접미사가_있는_지명():
    assert parse_constraints("성수동 오후 3시간").region == "성수동"
    assert parse_constraints("강남역에서 회식").region == "강남역"


def test_접미사가_없는_지명도_인식한다():
    assert parse_constraints("홍대에서 놀자").region == "홍대"
    assert parse_constraints("가로수길 브런치").region == "가로수길"
    assert parse_constraints("해운대 저녁").region == "해운대"


def test_지명이_없으면_None():
    assert parse_constraints("아무데나 놀고 싶어").region is None


def test_지역_미인식이면_응답에서_알린다():
    uid = client.post("/signup", json={"phone": "010-9999-0000"}).json()["user_id"]
    cid = client.post("/courses", headers={"X-User-Id": uid}).json()["id"]
    res = client.post(
        f"/courses/{cid}/generate",
        json={"text": "오전 10시 5시간 도보"},
        headers={"X-User-Id": uid},
    )
    assert res.status_code == 200

    messages = client.get(f"/courses/{cid}/messages").json()
    assert any("지역을 못 알아들어" in m["text"] for m in messages if m["role"] == "ai")


def test_지역을_인식하면_안내하지_않는다():
    uid = client.post("/signup", json={"phone": "010-9999-1111"}).json()["user_id"]
    cid = client.post("/courses", headers={"X-User-Id": uid}).json()["id"]
    client.post(
        f"/courses/{cid}/generate",
        json={"text": "홍대 오전 10시 5시간 도보"},
        headers={"X-User-Id": uid},
    )
    messages = client.get(f"/courses/{cid}/messages").json()
    assert not any("지역을 못 알아들어" in m["text"] for m in messages if m["role"] == "ai")
