"""운영 자동 QA: 전용 세션 발급과 학습 신호 차단."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import api

QA = "q" * 40


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "qa_token", QA)
    return TestClient(api)


def test_토큰이_없거나_틀리면_QA_세션은_없는_척(client, monkeypatch):
    assert client.post("/admin/qa-session").status_code == 404
    assert client.post("/admin/qa-session", headers={"X-QA-Token": "nope"}).status_code == 404
    monkeypatch.setattr(settings, "qa_token", "")
    assert client.post("/admin/qa-session", headers={"X-QA-Token": ""}).status_code == 404


def test_QA_세션은_늘_같은_전용_회원(client):
    a = client.post("/admin/qa-session", headers={"X-QA-Token": QA}).json()
    b = client.post("/admin/qa-session", headers={"X-QA-Token": QA}).json()
    assert a["user_id"] == b["user_id"] and a["kind"] == "member"


def test_QA_요청은_학습_신호를_쌓지_않는다(client):
    """하루 여러 번 도는 점검이 같은 장소를 '인기'로 만들면 실제 추천이 왜곡된다."""
    from app.popularity import popularity_store

    qa = client.post("/admin/qa-session", headers={"X-QA-Token": QA}).json()
    h = {"X-User-Id": qa["user_id"], "X-QA-Token": QA}
    cid = client.post("/courses", headers=h).json()["id"]
    # 앞 테스트가 같은 목업 장소에 쌓은 값이 있을 수 있다 — 전후 차이로 본다
    probe = client.post(f"/courses/{cid}/generate", json={"text": "성수동 오후 2시 3시간"}, headers=h).json()["course"]
    ids = [it["place"]["id"] for it in probe["items"]]
    assert ids
    before = popularity_store.scores(ids)
    client.post(f"/courses/{cid}/generate", json={"text": "성수동 오후 2시 3시간"}, headers=h)
    after = popularity_store.scores(ids)
    assert all(abs(after[i] - before[i]) < 0.01 for i in ids)

    # 같은 흐름을 QA 표시 없이 하면 쌓인다(대조)
    h2 = {"X-User-Id": qa["user_id"]}
    client.post(f"/courses/{cid}/generate", json={"text": "성수동 오후 2시 3시간"}, headers=h2)
    assert any(popularity_store.scores(ids)[i] > after[i] + 0.5 for i in ids)


def test_QA_표시는_요청이_끝나면_풀린다(client):
    from app.qa import learning_on

    client.get("/health", headers={"X-QA-Token": QA})
    assert learning_on() is True


def test_QA_요청은_사람_몫에_걸리지_않지만_서비스_상한은_센다(client, monkeypatch):
    from app import usage

    monkeypatch.setitem(usage.LIMITS, "course", usage.Limit(guest=0, member=1))
    qa = client.post("/admin/qa-session", headers={"X-QA-Token": QA}).json()
    h = {"X-User-Id": qa["user_id"], "X-QA-Token": QA}
    for _ in range(3):
        assert client.post("/courses", headers=h).status_code == 200
    assert usage.global_used("course") == 3
    # 토큰 없이 같은 계정이면 회원 몫(1개)에 걸린다
    assert client.post("/courses", headers={"X-User-Id": qa["user_id"]}).status_code == 200
    assert client.post("/courses", headers={"X-User-Id": qa["user_id"]}).status_code == 429
