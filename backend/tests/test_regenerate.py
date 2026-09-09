"""'다시 해줘' 는 직전 조건을 그대로 다시 쓴다."""
from __future__ import annotations

import itertools

from fastapi.testclient import TestClient

from app.main import api

client = TestClient(api)
_phones = itertools.count(1)


def _course() -> tuple[str, str]:
    uid = client.post(
        "/signup", json={"phone": f"010-4343-{next(_phones):04d}"}
    ).json()["user_id"]
    cid = client.post("/courses", headers={"X-User-Id": uid}).json()["id"]
    client.post(
        f"/courses/{cid}/generate",
        headers={"X-User-Id": uid},
        json={"text": "성수동 오전 10시 5시간 도보"},
    )
    return uid, cid


def test_다시_해줘는_직전_조건을_유지한다():
    uid, cid = _course()
    client.post(
        f"/courses/{cid}/generate", headers={"X-User-Id": uid}, json={"text": "다시 해줘"}
    )
    body = client.get(f"/courses/{cid}").json()
    assert body["region"] == "성수동"
    assert body["items"][0]["arrive"].startswith("10:00")


def test_새로_만들어줘도_같은_조건으로():
    uid, cid = _course()
    client.post(
        f"/courses/{cid}/generate", headers={"X-User-Id": uid}, json={"text": "새로 만들어줘"}
    )
    assert client.get(f"/courses/{cid}").json()["region"] == "성수동"


def test_편집_요청_뒤에도_원래_조건을_찾는다():
    uid, cid = _course()
    client.post(
        f"/courses/{cid}/generate", headers={"X-User-Id": uid}, json={"text": "2번째 빼줘"}
    )
    client.post(
        f"/courses/{cid}/generate", headers={"X-User-Id": uid}, json={"text": "다시 해줘"}
    )
    body = client.get(f"/courses/{cid}").json()
    assert body["region"] == "성수동"
    assert len(body["items"]) >= 2  # 편집 이전 조건으로 다시 만들었다
