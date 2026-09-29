"""별점·재방문 신호는 서명된 신원(없으면 IP)으로만 한 사람을 센다."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import api
from tests.helpers import member


@pytest.fixture
def client():
    from app.ratings import rating_store, user_rating_store
    from app.revisits import revisit_store

    for s in (rating_store, user_rating_store, revisit_store):
        getattr(s, "_mem", {}).clear()
    return TestClient(api)


def test_익명_별점은_IP_하나를_한_사람으로_센다(client):
    """예전: 로그인 없이 보내면 매번 표본이 늘어 반복 제출로 평균을 흔들 수 있었다."""
    for _ in range(5):
        client.post("/places/p-anon/rating", json={"stars": 1})
    client.post("/places/p-anon/rating", json={"stars": 5}, headers={"X-User-Id": member(client)})
    avg = client.post("/places/p-anon/rating", json={"stars": 1}).json()["average"]
    assert avg == pytest.approx(3.0)  # (1 + 5) / 2 — 익명 다섯 번은 한 표


def test_서명이_틀린_id_는_그_사람으로_세지_않는다(client, monkeypatch):
    monkeypatch.setattr(settings, "session_secret", "s" * 40)
    forged = {"X-User-Id": "victim", "X-User-Token": "1.bad"}
    assert client.post("/places/p-r/revisit", headers=forged).json()["counted"] is False
    for i in range(3):  # id 를 바꿔 적어도 익명(IP) 한 표
        client.post("/places/p-f/rating", json={"stars": 1}, headers={"X-User-Id": f"fake{i}"})
    avg = client.post("/places/p-f/rating", json={"stars": 1}).json()
    assert avg["counted"] is False


def test_재방문은_서명된_계정만_한_번(client):
    uid = member(client)
    h = {"X-User-Id": uid}
    assert client.post("/places/p-v/revisit", headers=h).json()["counted"] is True
    assert client.post("/places/p-v/revisit", headers=h).json()["counted"] is False
    assert client.post("/places/p-v/revisit").json()["counted"] is False
