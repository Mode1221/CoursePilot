"""별점은 사람·장소당 한 표. 다시 매기면 이전 점수를 대체한다."""
from __future__ import annotations

import itertools

from fastapi.testclient import TestClient

from app.main import api
from app.ratings import rating_store, user_rating_store

client = TestClient(api)
_phones = itertools.count(1)


def _user() -> str:
    return client.post(
        "/signup", json={"phone": f"010-5959-{next(_phones):04d}"}
    ).json()["user_id"]


def _avg(pid: str) -> float | None:
    return rating_store.averages([pid]).get(pid)


def test_같은_사람이_반복_제출해도_표본이_늘지_않는다():
    user_rating_store.clear()
    rating_store._mem.clear()
    uid = _user()
    for _ in range(5):
        client.post("/places/pr-1/rating", headers={"X-User-Id": uid}, json={"stars": 5})
    client.post("/places/pr-1/rating", headers={"X-User-Id": _user()}, json={"stars": 1})
    # 5점 한 표 + 1점 한 표 = 평균 3.0 (5점이 5표로 부풀지 않는다)
    assert _avg("pr-1") == 3.0


def test_점수를_바꾸면_이전_점수를_대체한다():
    user_rating_store.clear()
    rating_store._mem.clear()
    uid = _user()
    client.post("/places/pr-2/rating", headers={"X-User-Id": uid}, json={"stars": 5})
    assert _avg("pr-2") == 5.0
    client.post("/places/pr-2/rating", headers={"X-User-Id": uid}, json={"stars": 2})
    assert _avg("pr-2") == 2.0


def test_같은_점수_재제출은_집계하지_않는다():
    user_rating_store.clear()
    rating_store._mem.clear()
    uid = _user()
    first = client.post(
        "/places/pr-3/rating", headers={"X-User-Id": uid}, json={"stars": 4}
    ).json()
    again = client.post(
        "/places/pr-3/rating", headers={"X-User-Id": uid}, json={"stars": 4}
    ).json()
    assert first.get("counted") is not False
    assert again["counted"] is False
    assert _avg("pr-3") == 4.0
