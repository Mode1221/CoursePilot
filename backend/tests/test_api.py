
"""API 계층 통합 테스트 (TestClient, 인메모리 폴백). Socket.IO broadcast 는 no-op."""
import itertools

import pytest
from fastapi.testclient import TestClient

from app.main import api


@pytest.fixture
def client():
    return TestClient(api)


_phone_seq = itertools.count(1)


def _signup(client) -> str:
    # 같은 번호로 재가입하면 같은 계정(크레딧 유지)이므로 테스트마다 번호를 달리한다
    phone = f"010-0000-{next(_phone_seq):04d}"
    return client.post("/signup", json={"phone": phone}).json()["user_id"]


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

    left = client.get(f"/users/{uid}/credits", headers={"X-User-Id": uid}).json()["questions_left"]
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
    assert abs(after - (before - 1)) < 0.05  # -1 상쇄(미세 감쇠 허용)


def test_completion_signal_boosts_places(client):
    from app.popularity import popularity_store

    uid = _signup(client)
    course_id = client.post("/courses", headers={"X-User-Id": uid}).json()["id"]
    client.post(
        f"/courses/{course_id}/generate",
        headers={"X-User-Id": uid},
        json={"text": "성수동 오전 10시 5시간 도보"},
    )
    items = client.get(f"/courses/{course_id}").json()["items"]
    pid = items[0]["place"]["id"]
    before = popularity_store.scores([pid])[pid]

    res = client.post(f"/courses/{course_id}/complete")
    assert res.status_code == 200
    assert res.json()["places"] == len(items)
    after = popularity_store.scores([pid])[pid]
    assert after - before > 2.5  # 완주 가중(+3) 반영

    assert client.post("/courses/none/complete").status_code == 404


def test_view_signal_light_boost(client):
    from app.popularity import popularity_store

    uid = _signup(client)
    course_id = client.post("/courses", headers={"X-User-Id": uid}).json()["id"]
    client.post(
        f"/courses/{course_id}/generate",
        headers={"X-User-Id": uid},
        json={"text": "성수동 오전 10시 5시간 도보"},
    )
    pid = client.get(f"/courses/{course_id}").json()["items"][0]["place"]["id"]
    before = popularity_store.scores([pid])[pid]
    assert client.post(f"/courses/{course_id}/view").status_code == 200
    after = popularity_store.scores([pid])[pid]
    assert 0 < after - before < 0.5  # 약한 가점
    assert client.post("/courses/none/view").status_code == 404


def test_satisfaction_signal(client):
    from app.popularity import popularity_store

    uid = _signup(client)
    course_id = client.post("/courses", headers={"X-User-Id": uid}).json()["id"]
    client.post(
        f"/courses/{course_id}/generate",
        headers={"X-User-Id": uid},
        json={"text": "성수동 오전 10시 5시간 도보"},
    )
    pid = client.get(f"/courses/{course_id}").json()["items"][0]["place"]["id"]
    before = popularity_store.scores([pid])[pid]
    assert client.post(f"/courses/{course_id}/satisfaction", json={"liked": True}).status_code == 200
    up = popularity_store.scores([pid])[pid]
    assert up - before > 1.5  # 👍 +가점
    assert client.post(f"/courses/{course_id}/satisfaction", json={"liked": False}).status_code == 200
    down = popularity_store.scores([pid])[pid]
    assert down < up  # 👎 -가점
    assert client.post("/courses/none/satisfaction", json={"liked": True}).status_code == 404


def test_revisit_signal(client):
    from app.popularity import popularity_store

    uid = _signup(client)
    before = popularity_store.scores(["place-revisit"])["place-revisit"]
    res = client.post("/places/place-revisit/revisit", headers={"X-User-Id": uid})
    assert res.status_code == 200 and res.json()["counted"] is True
    after = popularity_store.scores(["place-revisit"])["place-revisit"]
    assert after - before > 1.5  # 재방문 의사 강한 가점


def test_admin_signals_shape(client):
    res = client.get("/admin/signals")
    assert res.status_code == 200
    body = res.json()
    assert set(body) == {
        "feedback_counts",
        "relax_acceptance_rate",
        "relax_offered",
        "relax_applied",
        "satisfaction_rate",
        "completed_count",
        "seed_strategy_counts",
        "score_satisfaction_separation",
        "preferences",
    }
    assert isinstance(body["feedback_counts"], dict)
    assert 0.0 <= body["relax_acceptance_rate"] <= 1.0


def test_add_place_from_repo(client):
    from app.places import place_repo
    from app.schemas import Place

    uid = _signup(client)
    course_id = client.post("/courses", headers={"X-User-Id": uid}).json()["id"]
    client.post(
        f"/courses/{course_id}/generate",
        headers={"X-User-Id": uid},
        json={"text": "성수동 오전 10시 5시간 도보"},
    )
    before = len(client.get(f"/courses/{course_id}").json()["items"])
    place_repo.upsert_many(
        [Place(id="extra-1", name="추가장소", category="카페", lat=37.5, lng=127.0, rating=4.0)]
    )

    res = client.post(f"/courses/{course_id}/places", json={"place_id": "extra-1"})
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == before + 1
    assert any(it["place"]["id"] == "extra-1" for it in items)

    # 중복 추가 방지
    dup = client.post(f"/courses/{course_id}/places", json={"place_id": "extra-1"})
    assert dup.status_code == 409
    # 미등록 장소
    assert client.post(f"/courses/{course_id}/places", json={"place_id": "nope"}).status_code == 404


def test_bookmark_flow(client):
    uid = _signup(client)
    course_id = client.post("/courses", headers={"X-User-Id": uid}).json()["id"]
    assert client.put(f"/users/{uid}/bookmarks/{course_id}", headers={"X-User-Id": uid}).status_code == 200
    marks = client.get(f"/users/{uid}/bookmarks", headers={"X-User-Id": uid}).json()
    assert any(c["id"] == course_id for c in marks)
