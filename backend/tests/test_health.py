"""liveness / readiness 프로브."""
from fastapi.testclient import TestClient

from app.config import settings
from app.main import api


def test_health_is_always_ok():
    with TestClient(api) as client:
        assert client.get("/health").json() == {"status": "ok"}


def test_readiness_reports_state_in_development():
    # 개발에서는 DB 가 없어도 트래픽을 받는다(인메모리 폴백)
    with TestClient(api) as client:
        res = client.get("/health/ready")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"


def test_readiness_fails_in_production_without_db(monkeypatch):
    # 운영에서 DB 가 안 붙었으면 조용히 인메모리로 돌지 말고 빠져야 한다
    monkeypatch.setattr(settings, "env", "production")
    monkeypatch.setattr(settings, "session_secret", "s")
    monkeypatch.setattr(settings, "admin_token", "t")
    with TestClient(api) as client:
        res = client.get("/health/ready")
        assert res.status_code == 503
        assert res.json()["db"] is False


def test_readiness_reports_missing_settings_without_values(monkeypatch):
    monkeypatch.setattr(settings, "env", "production")
    monkeypatch.setattr(settings, "session_secret", "")
    monkeypatch.setattr(settings, "admin_token", "")
    with TestClient(api) as client:
        body = client.get("/health/ready").json()
        assert set(body["missing_settings"]) == {"SESSION_SECRET", "ADMIN_TOKEN"}
