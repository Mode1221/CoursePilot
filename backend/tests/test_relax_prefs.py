"""완화 재시도도 온보딩 선호를 반영한다."""
from __future__ import annotations

import itertools

from fastapi.testclient import TestClient

from app.main import api

client = TestClient(api)
_phones = itertools.count(1)


def _user() -> str:
    return client.post(
        "/signup", json={"phone": f"010-6161-{next(_phones):04d}"}
    ).json()["user_id"]


def test_완화_재시도에_선호_프로필이_전달된다(monkeypatch):
    uid = _user()
    client.put(
        f"/users/{uid}/preferences",
        headers={"X-User-Id": uid},
        json={"mood": "조용한", "region": "연남동", "budget": "2~4만원", "diet": ["비건"]},
    )
    cid = client.post("/courses", headers={"X-User-Id": uid}).json()["id"]
    client.post(
        f"/courses/{cid}/generate",
        headers={"X-User-Id": uid},
        json={"text": "저녁에 놀 데 찾아줘"},
    )

    seen: list[dict | None] = []
    import app.main as main
    real = main.generate_course

    async def _spy(text, map_service, preferences=None, on_progress=None, force_relax=False):
        seen.append(preferences)
        return await real(text, map_service, preferences, on_progress, force_relax)

    monkeypatch.setattr(main, "generate_course", _spy)
    client.post(f"/courses/{cid}/relax", headers={"X-User-Id": uid})

    assert seen and seen[-1] is not None
    assert seen[-1]["region"] == "연남동"
    assert seen[-1]["budget"] == "2~4만원"
    assert seen[-1]["diet"] == ["비건"]
    assert "behavior_cats" in seen[-1]
