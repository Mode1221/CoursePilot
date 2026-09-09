"""선호 프로필 조회 — 설정 화면 재진입 시 기존 값 복원용."""
from __future__ import annotations

import itertools

from fastapi.testclient import TestClient

from app.main import api

client = TestClient(api)
_phones = itertools.count(1)


def _user() -> str:
    return client.post(
        "/signup", json={"phone": f"010-2727-{next(_phones):04d}"}
    ).json()["user_id"]


def test_저장한_선호를_돌려준다():
    uid = _user()
    prefs = {
        "mood": "조용한",
        "region": "연남동",
        "transport": "도보",
        "budget": "2~4만원",
        "diet": ["비건"],
    }
    client.put(f"/users/{uid}/preferences", headers={"X-User-Id": uid}, json=prefs)
    got = client.get(f"/users/{uid}/preferences", headers={"X-User-Id": uid}).json()
    assert got == prefs


def test_저장_전에는_빈_프로필():
    uid = _user()
    got = client.get(f"/users/{uid}/preferences", headers={"X-User-Id": uid}).json()
    assert got["mood"] is None and got["diet"] == []


def test_남의_선호는_볼_수_없다():
    uid, other = _user(), _user()
    res = client.get(f"/users/{uid}/preferences", headers={"X-User-Id": other})
    assert res.status_code == 403


def test_없는_사용자는_404():
    res = client.get("/users/nope/preferences", headers={"X-User-Id": "nope"})
    assert res.status_code == 404
