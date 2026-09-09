"""레퍼럴 보너스 상한 — 번호만 바꿔 무한 초대하는 것을 막는다."""
from __future__ import annotations

import itertools

from fastapi.testclient import TestClient

from app.main import REFERRAL_BONUS, api
from app.users import MAX_REFERRAL_BONUS

client = TestClient(api)
_phones = itertools.count(1)


def _phone() -> str:
    return f"010-7171-{next(_phones):04d}"


def _credits(uid: str) -> int:
    return client.get(f"/users/{uid}/credits", headers={"X-User-Id": uid}).json()[
        "questions_left"
    ]


def test_상한까지만_보너스를_준다():
    uid = client.post("/signup", json={"phone": _phone()}).json()["user_id"]
    base = _credits(uid)
    for _ in range(MAX_REFERRAL_BONUS + 5):
        client.post("/signup", json={"phone": _phone(), "referrer_id": uid})
    assert _credits(uid) == base + MAX_REFERRAL_BONUS * REFERRAL_BONUS


def test_초대_한_건은_그대로_지급된다():
    uid = client.post("/signup", json={"phone": _phone()}).json()["user_id"]
    base = _credits(uid)
    client.post("/signup", json={"phone": _phone(), "referrer_id": uid})
    assert _credits(uid) == base + REFERRAL_BONUS


def test_없는_초대자는_무시한다():
    res = client.post("/signup", json={"phone": _phone(), "referrer_id": "nope"})
    assert res.status_code == 200
