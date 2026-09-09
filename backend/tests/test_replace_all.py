"""'전부 다른 곳으로' — 조건은 유지하고 장소만 갈아 끼운다."""
from __future__ import annotations

import itertools

from fastapi.testclient import TestClient

from app.main import api

client = TestClient(api)
_phones = itertools.count(1)


def _course() -> tuple[str, str, list[str]]:
    uid = client.post(
        "/signup", json={"phone": f"010-5555-{next(_phones):04d}"}
    ).json()["user_id"]
    cid = client.post("/courses", headers={"X-User-Id": uid}).json()["id"]
    client.post(
        f"/courses/{cid}/generate",
        headers={"X-User-Id": uid},
        json={"text": "성수동 오전 10시 5시간 도보"},
    )
    ids = [i["place"]["id"] for i in client.get(f"/courses/{cid}").json()["items"]]
    return uid, cid, ids


def test_기존_장소를_피해서_다시_고른다():
    uid, cid, before = _course()
    client.post(
        f"/courses/{cid}/generate",
        headers={"X-User-Id": uid},
        json={"text": "전부 다른 곳으로 바꿔줘"},
    )
    body = client.get(f"/courses/{cid}").json()
    after = [i["place"]["id"] for i in body["items"]]

    assert after and not (set(before) & set(after))  # 겹치는 장소가 없다
    assert body["region"] == "성수동"  # 조건(지역)은 그대로


def test_여기_말고_다른_데로도_같은_처리():
    uid, cid, before = _course()
    client.post(
        f"/courses/{cid}/generate",
        headers={"X-User-Id": uid},
        json={"text": "여기 말고 다른 곳들로"},
    )
    body = client.get(f"/courses/{cid}").json()
    assert body["region"] == "성수동"
    assert not (set(before) & {i["place"]["id"] for i in body["items"]})
