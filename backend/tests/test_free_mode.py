"""검증 기간 무료(free_mode): 크레딧을 차감하지 않고, 환불도 하지 않으며, 프론트에 알린다."""
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import api
from app.quota import QuotaStore
from app.users import CreditError, UserStore


def test_free_mode_는_크레딧을_차감하지_않는다(monkeypatch):
    monkeypatch.setattr(settings, "free_mode", True)
    us = UserStore()
    user = us.create("010-9999-0001", credits_limit=1)
    for _ in range(5):
        us.consume_credit(user.id)
    assert us.get(user.id).credits_left == 1


def test_free_mode_에서도_없는_계정은_거부(monkeypatch):
    monkeypatch.setattr(settings, "free_mode", True)
    with pytest.raises(CreditError):
        UserStore().consume_credit("no-such-user")


def test_free_mode_환불은_포인트를_늘리지_않는다(monkeypatch):
    monkeypatch.setattr(settings, "free_mode", True)
    us = UserStore()
    user = us.create("010-9999-0002", credits_limit=1)
    us.consume_credit(user.id)
    us.refund_credit(user.id)
    got = us.get(user.id)
    assert got.points == 0 and got.credits_used == 0


def test_credits_응답에_free_mode_가_실린다(monkeypatch):
    monkeypatch.setattr(settings, "free_mode", True)
    monkeypatch.setattr(settings, "session_secret", "")
    from app.accounts_api import user_store as store

    user = store.create("010-9999-0003")
    client = TestClient(api)
    r = client.get(f"/users/{user.id}/credits", headers={"X-User-Id": user.id})
    assert r.status_code == 200
    assert r.json()["free_mode"] is True


def test_health_에_free_mode_와_ai_notice(monkeypatch):
    monkeypatch.setattr(settings, "free_mode", True)
    client = TestClient(api)
    body = client.get("/health").json()
    assert body["free_mode"] is True
    assert "AI" in body["ai_notice"]


def test_폴백_일일_상한은_설정을_따른다(monkeypatch):
    monkeypatch.setattr(settings, "hours_fallback_daily_cap", 2)
    q = QuotaStore()
    assert q.daily_limit("llm.hours_fallback") == 2
    assert q.allow_today("llm.hours_fallback")
    q.record_today("llm.hours_fallback", 2)
    assert not q.allow_today("llm.hours_fallback")
