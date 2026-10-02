"""운영 지표(/admin/ops-stats) — Atelier 본부로 보내는 날짜별 집계."""
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.config import settings
from app.funnel import funnel_store
from app.main import api
from app.ops_stats import SERIES, daily_stats
from app.referrals import Acquisition, referral_store

client = TestClient(api)


def test_날짜별_체험_가입_퍼널과_출처를_센다():
    now = datetime(2026, 10, 1, 3, 0)  # UTC = 한국 12시
    referral_store.save(Acquisition(user_id="g1", source="threads", guest_at=now - timedelta(hours=1)))
    referral_store.save(Acquisition(user_id="g2", source=None, guest_at=now - timedelta(days=1), member_at=now))
    # UTC 전날 20시 = 한국 오늘 05시 → 오늘로 센다
    referral_store.save(Acquisition(user_id="g3", source="x", guest_at=datetime(2026, 9, 30, 20, 0)))
    funnel_store.record("built", "c1", at=datetime.now())
    s = daily_stats(days=14, now=now)
    assert len(s["days"]) == 14 and s["days"][-1]["date"] == "2026-10-01"
    today = s["days"][-1]
    assert today["guests"] == 2 and today["signups"] == 1
    assert s["days"][-2]["guests"] == 1
    assert s["sources"] == {"threads": 1, "direct": 1, "x": 1}
    assert list(s["series"]) == list(SERIES) and next(iter(s["series"])) == "visitors"
    assert s["totals"]["최근 7일 새 체험"] == 3


def test_QA_토큰이나_관리자_토큰으로만_열린다(monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "adm")
    monkeypatch.setattr(settings, "qa_token", "qa-secret")
    assert client.get("/admin/ops-stats").status_code == 401
    assert client.get("/admin/ops-stats", headers={"X-QA-Token": "wrong"}).status_code == 401
    r = client.get("/admin/ops-stats", headers={"X-QA-Token": "qa-secret"})
    assert r.status_code == 200 and "days" in r.json()
    assert client.get("/admin/ops-stats", headers={"X-Admin-Token": "adm"}).status_code == 200
    body = r.text
    assert "user_id" not in body and "g1" not in body
