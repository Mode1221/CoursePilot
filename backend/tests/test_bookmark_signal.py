"""북마크 신호는 반복해도 한 번, 해제하면 되돌린다."""
from __future__ import annotations

import itertools

from fastapi.testclient import TestClient

from app.main import api
from app.popularity import popularity_store

client = TestClient(api)
_phones = itertools.count(1)


def _course() -> tuple[str, str, str]:
    uid = client.post(
        "/signup", json={"phone": f"010-8686-{next(_phones):04d}"}
    ).json()["user_id"]
    cid = client.post("/courses", headers={"X-User-Id": uid}).json()["id"]
    client.post(
        f"/courses/{cid}/generate",
        headers={"X-User-Id": uid},
        json={"text": "성수동 오전 10시 5시간 도보"},
    )
    pid = client.get(f"/courses/{cid}").json()["items"][0]["place"]["id"]
    return uid, cid, pid


def test_반복_북마크는_한_번만_센다():
    uid, cid, pid = _course()
    before = popularity_store.scores([pid])[pid]
    results = [
        client.put(f"/users/{uid}/bookmarks/{cid}", headers={"X-User-Id": uid}).json()["added"]
        for _ in range(4)
    ]
    after = popularity_store.scores([pid])[pid]

    assert results == [True, False, False, False]
    assert 1.5 < after - before < 2.5


def test_해제하면_가점을_되돌린다():
    uid, cid, pid = _course()
    before = popularity_store.scores([pid])[pid]
    client.put(f"/users/{uid}/bookmarks/{cid}", headers={"X-User-Id": uid})
    client.delete(f"/users/{uid}/bookmarks/{cid}", headers={"X-User-Id": uid})
    after = popularity_store.scores([pid])[pid]
    assert abs(after - before) < 0.1


def test_없던_북마크_해제는_아무_일도_없다():
    uid, cid, pid = _course()
    before = popularity_store.scores([pid])[pid]
    res = client.delete(f"/users/{uid}/bookmarks/{cid}", headers={"X-User-Id": uid})
    after = popularity_store.scores([pid])[pid]
    assert res.json()["removed"] is False
    assert abs(after - before) < 0.05
