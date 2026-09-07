"""API 계층 통합 테스트 (TestClient, 인메모리 폴백). Socket.IO broadcast 는 no-op."""
import pytest
from fastapi.testclient import TestClient

from app.main import api


@pytest.fixture
def client():
    return TestClient(api)


def _signup(client) -> str:
    return client.post("/signup", json={"phone": "010-0000-0000"}).json()["user_id"]


def test_participant_cannot_use_ai(client):
    course_id = client.post("/courses").json()["id"]
    res = client.post(f"/courses/{course_id}/generate", json={"text": "성수동 코스"})
    assert res.status_code == 403


def test_creator_generates_and_consumes_credit(client):
    uid = _signup(client)
    course_id = client.post("/courses", headers={"X-User-Id": uid}).json()["id"]

    res = client.post(
        f"/courses/{course_id}/generate",
        headers={"X-User-Id": uid},
        json={"text": "성수동 오전 10시 5시간 코스 도보"},
    )
    assert res.status_code == 200
    body = res.json()
    assert len(body["course"]["items"]) >= 3

    left = client.get(f"/users/{uid}/credits").json()["questions_left"]
    assert left == 4  # 5 → 4


def test_manual_reorder_keeps_start_and_serializes(client):
    uid = _signup(client)
    course_id = client.post("/courses", headers={"X-User-Id": uid}).json()["id"]
    client.post(
        f"/courses/{course_id}/generate",
        headers={"X-User-Id": uid},
        json={"text": "성수동 오전 10시 5시간 도보"},
    )
    items = client.get(f"/courses/{course_id}").json()["items"]
    ids = [it["place"]["id"] for it in reversed(items)]

    res = client.post(f"/courses/{course_id}/reorder", json={"place_ids": ids})
    assert res.status_code == 200
    reordered = res.json()["items"]
    assert reordered[0]["arrive"] == items[0]["arrive"]  # 시작 시각 유지
    assert [it["place"]["id"] for it in reordered] == ids


def test_credit_exhaustion_returns_402(client):
    uid = _signup(client)
    course_id = client.post("/courses", headers={"X-User-Id": uid}).json()["id"]
    for _ in range(5):
        client.post(
            f"/courses/{course_id}/generate",
            headers={"X-User-Id": uid},
            json={"text": "성수동 5시간 도보"},
        )
    res = client.post(
        f"/courses/{course_id}/generate",
        headers={"X-User-Id": uid},
        json={"text": "성수동 5시간 도보"},
    )
    assert res.status_code == 402


def test_manual_removal_demotes_place(client):
    from app.popularity import popularity_store

    uid = _signup(client)
    course_id = client.post("/courses", headers={"X-User-Id": uid}).json()["id"]
    client.post(
        f"/courses/{course_id}/generate",
        headers={"X-User-Id": uid},
        json={"text": "성수동 오전 10시 5시간 도보"},
    )
    items = client.get(f"/courses/{course_id}").json()["items"]
    removed_id = items[0]["place"]["id"]
    keep_ids = [it["place"]["id"] for it in items[1:]]
    before = popularity_store.scores([removed_id])[removed_id]

    # 첫 장소 삭제(수동 편집) → 해당 장소 인기 -1 상쇄
    client.post(f"/courses/{course_id}/reorder", json={"place_ids": keep_ids})
    after = popularity_store.scores([removed_id])[removed_id]
    assert after == before - 1


def test_bookmark_flow(client):
    uid = _signup(client)
    course_id = client.post("/courses", headers={"X-User-Id": uid}).json()["id"]
    assert client.put(f"/users/{uid}/bookmarks/{course_id}").status_code == 200
    marks = client.get(f"/users/{uid}/bookmarks").json()
    assert any(c["id"] == course_id for c in marks)
