"""측정 장치 — 퍼널·합의 시간·역할 역전·30일 재사용."""
import itertools
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.funnel import Event, funnel_store, summarize
from app.main import api

T0 = datetime(2026, 9, 22, 12, 0)


def _e(name, cid, actor=None, dev=None, uid=None, mins=0):
    return Event(name, cid, actor, dev, uid, T0 + timedelta(minutes=mins))


def test_퍼널_비율과_합의_시간():
    ev = [
        _e("started", "c1", "owner", "d-owner", "u1"), _e("link_opened", "c1", "partner", "d-p", mins=5),
        _e("partner_card", "c1", "partner", "d-p", mins=6), _e("built", "c1", mins=10), _e("built_both", "c1", mins=10),
        _e("confirmed", "c1", mins=16), _e("completed", "c1", mins=2000),
        _e("started", "c2", "owner", "d-o2", "u2"), _e("link_opened", "c2", "partner", "d-p2", mins=1),
    ]
    s = summarize(ev)
    assert s["rates"]["link_open_rate"] == 1.0
    assert s["rates"]["partner_card_rate"] == 0.5  # 2명 열고 1명만 냄
    assert s["rates"]["confirmed_rate"] == 1.0
    assert s["median_minutes"]["partner_card_to_confirmed"] == 10.0


def test_역할_역전은_상대였던_기기가_나중에_시작할_때():
    ev = [
        _e("partner_card", "c1", "partner", "d-jieun", mins=0),
        _e("started", "c9", "owner", "d-jieun", mins=60 * 24 * 7),  # 일주일 뒤 지은이 먼저 시작
        _e("started", "c5", "owner", "d-x", mins=-10),
    ]
    s = summarize(ev)
    assert s["role_reversals"] == 1 and s["partners_seen"] == 1


def test_30일_재사용():
    ev = [_e("started", "a", "owner", uid="u1"), _e("started", "b", "owner", uid="u1", mins=60 * 24 * 20),
          _e("started", "c", "owner", uid="u2"), _e("started", "d", "owner", uid="u2", mins=60 * 24 * 45)]
    assert summarize(ev)["repeat_starters_30d"] == 1


_seq = itertools.count(8100)


@pytest.fixture
def client():
    funnel_store.reset()
    return TestClient(api)


def test_합의_흐름을_따라가면_이벤트가_쌓이고_관리_지표에_나온다(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "admin_token", "")
    uid = client.post("/signup", json={"phone": f"010-0000-{next(_seq):04d}"}).json()["user_id"]
    h = {"X-User-Id": uid, "X-Device-Id": "dev-owner"}
    cid = client.post("/courses", headers=h).json()["id"]
    client.post(f"/courses/{cid}/together", json={"text": "토요일 3시 성수", "owner_name": "민수", "partner_name": "지은"}, headers=h)
    tok = client.get(f"/courses/{cid}/together/link", headers=h).json()["token"]
    ph = {"X-Device-Id": "dev-jieun"}
    client.get(f"/together/{tok}", headers=ph)
    client.get(f"/together/{tok}", headers=ph)  # 두 번 열어도 1회
    client.post(f"/courses/{cid}/together/input", json={"cravings": ["고기"]}, headers=h)
    client.post(f"/together/{tok}/input", json={"cravings": ["디저트"]}, headers=ph)
    client.post(f"/courses/{cid}/together/build", headers=h)
    client.post(f"/together/{tok}/accept", headers=ph)
    client.post(f"/courses/{cid}/together/accept", headers=h)
    client.post(f"/courses/{cid}/complete")
    m = client.get("/admin/together").json()
    c = m["counts"]
    assert c["started"] == 1 and c["link_opened"] == 1 and c["partner_card"] == 1 and c["owner_card"] == 1
    assert c["built_both"] == 1 and c["confirmed"] == 1 and c["completed"] == 1
    assert m["rates"]["partner_card_rate"] == 1.0
