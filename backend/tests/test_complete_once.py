"""완주 신호는 코스당 한 번만 반영한다."""
from __future__ import annotations

import itertools

from fastapi.testclient import TestClient

from app.main import api
from app.popularity import popularity_store

client = TestClient(api)
_phones = itertools.count(1)


def _course() -> tuple[str, str]:
    uid = client.post(
        "/signup", json={"phone": f"010-6464-{next(_phones):04d}"}
    ).json()["user_id"]
    cid = client.post("/courses", headers={"X-User-Id": uid}).json()["id"]
    client.post(
        f"/courses/{cid}/generate",
        headers={"X-User-Id": uid},
        json={"text": "성수동 오전 10시 5시간 도보"},
    )
    return uid, cid


def test_두_번_눌러도_인기_신호는_한_번만():
    _, cid = _course()
    pid = client.get(f"/courses/{cid}").json()["items"][0]["place"]["id"]
    before = popularity_store.scores([pid])[pid]

    first = client.post(f"/courses/{cid}/complete").json()
    mid = popularity_store.scores([pid])[pid]
    second = client.post(f"/courses/{cid}/complete").json()
    after = popularity_store.scores([pid])[pid]

    assert first["already"] is False
    assert second["already"] is True
    assert mid - before > 2.5  # 완주 가중 반영
    assert abs(after - mid) < 0.05  # 두 번째는 누적되지 않는다


def test_완주_여부가_코스_상태에_남는다():
    _, cid = _course()
    assert client.get(f"/courses/{cid}").json()["completed"] is False
    client.post(f"/courses/{cid}/complete")
    assert client.get(f"/courses/{cid}").json()["completed"] is True
