"""재방문 의사는 사람·장소당 한 번만 신호가 된다."""
from __future__ import annotations

import itertools

from fastapi.testclient import TestClient

from app.main import api
from app.popularity import popularity_store
from app.revisits import revisit_store

client = TestClient(api)
_phones = itertools.count(1)


def _user() -> str:
    return client.post(
        "/signup", json={"phone": f"010-3131-{next(_phones):04d}"}
    ).json()["user_id"]


def test_같은_사람이_반복하면_한_번만_센다():
    revisit_store.clear()
    uid = _user()
    before = popularity_store.scores(["p-rv-1"])["p-rv-1"]
    results = [
        client.post("/places/p-rv-1/revisit", headers={"X-User-Id": uid}).json()["counted"]
        for _ in range(4)
    ]
    after = popularity_store.scores(["p-rv-1"])["p-rv-1"]

    assert results == [True, False, False, False]
    assert 1.5 < after - before < 3.5


def test_다른_사람은_각각_센다():
    revisit_store.clear()
    a, b = _user(), _user()
    before = popularity_store.scores(["p-rv-2"])["p-rv-2"]
    assert client.post("/places/p-rv-2/revisit", headers={"X-User-Id": a}).json()["counted"]
    assert client.post("/places/p-rv-2/revisit", headers={"X-User-Id": b}).json()["counted"]
    after = popularity_store.scores(["p-rv-2"])["p-rv-2"]
    assert after - before > 3.5  # 두 사람 몫


def test_로그인하지_않으면_세지_않는다():
    revisit_store.clear()
    before = popularity_store.scores(["p-rv-3"])["p-rv-3"]
    res = client.post("/places/p-rv-3/revisit")
    after = popularity_store.scores(["p-rv-3"])["p-rv-3"]
    assert res.json()["counted"] is False
    assert abs(after - before) < 0.05
