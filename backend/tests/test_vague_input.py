"""의미 없는 입력은 코스를 만들지 않고 되묻는다(크레딧도 보존)."""
from __future__ import annotations

import itertools

from fastapi.testclient import TestClient

from app.main import api
from app.pipeline.decomposition import is_actionable, parse_constraints

client = TestClient(api)
_phones = itertools.count(1)


def _user_course() -> tuple[str, str]:
    uid = client.post("/signup", json={"phone": f"010-4545-{next(_phones):04d}"}).json()["user_id"]
    cid = client.post("/courses", headers={"X-User-Id": uid}).json()["id"]
    return uid, cid


def test_판단_규칙():
    for text in ("ㅋㅋㅋ", "!!!", "asdf", "ㅇㅇ"):
        assert is_actionable(text, parse_constraints(text)) is False, text
    for text in ("성수동", "아무데나 추천해줘", "놀러 가자", "저녁에 뭐 먹지"):
        assert is_actionable(text, parse_constraints(text)) is True, text


def test_되묻고_코스를_만들지_않는다():
    uid, cid = _user_course()
    res = client.post(
        f"/courses/{cid}/generate", headers={"X-User-Id": uid}, json={"text": "ㅋㅋㅋ"}
    )
    assert res.status_code == 200
    assert res.json()["course"]["items"] == []
    assert "어떤 모임인지" in client.get(f"/courses/{cid}/messages").json()[-1]["text"]


def test_크레딧을_소모하지_않는다():
    uid, cid = _user_course()
    before = client.get(f"/users/{uid}/credits", headers={"X-User-Id": uid}).json()["questions_left"]
    client.post(f"/courses/{cid}/generate", headers={"X-User-Id": uid}, json={"text": "!!!"})
    after = client.get(f"/users/{uid}/credits", headers={"X-User-Id": uid}).json()["questions_left"]
    assert after == before
