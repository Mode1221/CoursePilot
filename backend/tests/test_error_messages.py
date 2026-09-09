"""사용자에게 그대로 보이는 오류 문구는 한국어여야 한다."""
from __future__ import annotations

import re

from fastapi.testclient import TestClient

from app.main import api

client = TestClient(api)
_ASCII_ONLY = re.compile(r"^[\x00-\x7F]+$")


def _detail(res) -> str:
    body = res.json()
    return body.get("detail", "") if isinstance(body, dict) else ""


def test_없는_코스_계정_장소_모두_한국어로_안내한다():
    cases = [
        client.get("/courses/nope"),
        client.get("/users/nope/credits", headers={"X-User-Id": "nope"}),
        client.post("/courses/nope/complete"),
    ]
    for res in cases:
        assert res.status_code == 404
        detail = _detail(res)
        assert detail and not _ASCII_ONLY.match(detail), detail
