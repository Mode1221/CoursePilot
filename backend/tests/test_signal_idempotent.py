"""열람·만족도 신호는 반복해도 부풀지 않는다."""
from __future__ import annotations

import itertools

from fastapi.testclient import TestClient

from app.main import api
from app.popularity import popularity_store

client = TestClient(api)
_phones = itertools.count(1)


def _course_place() -> tuple[str, str]:
    uid = client.post(
        "/signup", json={"phone": f"010-9797-{next(_phones):04d}"}
    ).json()["user_id"]
    cid = client.post("/courses", headers={"X-User-Id": uid}).json()["id"]
    client.post(
        f"/courses/{cid}/generate",
        headers={"X-User-Id": uid},
        json={"text": "성수동 오전 10시 5시간 도보"},
    )
    pid = client.get(f"/courses/{cid}").json()["items"][0]["place"]["id"]
    return cid, pid


def test_열람은_코스당_한_번만_반영된다():
    cid, pid = _course_place()
    before = popularity_store.scores([pid])[pid]
    first = client.post(f"/courses/{cid}/view").json()
    once = popularity_store.scores([pid])[pid]
    for _ in range(4):
        client.post(f"/courses/{cid}/view")
    after = popularity_store.scores([pid])[pid]

    assert first["already"] is False
    assert once > before
    assert abs(after - once) < 0.05


def test_같은_만족도를_반복해도_쌓이지_않는다():
    cid, pid = _course_place()
    before = popularity_store.scores([pid])[pid]
    for _ in range(5):
        client.post(f"/courses/{cid}/satisfaction", json={"liked": True})
    after = popularity_store.scores([pid])[pid]
    assert 1.5 < after - before < 2.5  # 한 번 분량만


def test_평가를_바꾸면_이전_효과를_되돌린다():
    cid, pid = _course_place()
    client.post(f"/courses/{cid}/satisfaction", json={"liked": True})
    liked = popularity_store.scores([pid])[pid]
    client.post(f"/courses/{cid}/satisfaction", json={"liked": False})
    disliked = popularity_store.scores([pid])[pid]
    # 👍(+2) 취소(-2) 후 👎(-2) → 순변화 -4
    assert -4.5 < disliked - liked < -3.5
    assert client.get(f"/courses/{cid}").json()["satisfaction"] is False
