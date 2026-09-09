"""조건 일부만 바꾸는 요청은 나머지 조건을 유지한다."""
from __future__ import annotations

import itertools

from fastapi.testclient import TestClient

from app.main import api

client = TestClient(api)
_phones = itertools.count(1)


def _course() -> tuple[str, str]:
    uid = client.post(
        "/signup", json={"phone": f"010-6060-{next(_phones):04d}"}
    ).json()["user_id"]
    cid = client.post("/courses", headers={"X-User-Id": uid}).json()["id"]
    client.post(
        f"/courses/{cid}/generate",
        headers={"X-User-Id": uid},
        json={"text": "성수동 오전 10시 5시간 도보"},
    )
    return uid, cid


def test_시간만_바꾸면_지역은_유지된다():
    uid, cid = _course()
    client.post(
        f"/courses/{cid}/generate",
        headers={"X-User-Id": uid},
        json={"text": "시간을 12시로 바꿔줘"},
    )
    body = client.get(f"/courses/{cid}").json()
    assert body["region"] == "성수동"
    assert body["items"][0]["arrive"].startswith("12:00")


def test_예산만_바꿔도_지역과_시간이_남는다():
    uid, cid = _course()
    client.post(
        f"/courses/{cid}/generate",
        headers={"X-User-Id": uid},
        json={"text": "예산을 5만원으로 올려줘"},
    )
    body = client.get(f"/courses/{cid}").json()
    assert body["region"] == "성수동"
    assert body["items"] and body["items"][0]["arrive"].startswith("10:00")


def test_인원_변경도_코스에_반영된다():
    uid, cid = _course()
    client.post(
        f"/courses/{cid}/generate",
        headers={"X-User-Id": uid},
        json={"text": "인원을 4명으로 바꿔줘"},
    )
    body = client.get(f"/courses/{cid}").json()
    assert body["party_size"] == 4
    assert body["region"] == "성수동"
