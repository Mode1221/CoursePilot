"""관리 엔드포인트 토큰 보호."""
from fastapi.testclient import TestClient

from app.config import settings
from app.main import api

client = TestClient(api)


def test_토큰_미설정이면_열려_있다():
    assert settings.admin_token == ""
    assert client.get("/admin/metrics").status_code == 200


def test_토큰_설정_시_일치해야_한다(monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "secret-token")
    assert client.get("/admin/metrics").status_code == 401
    assert client.get("/admin/metrics", headers={"X-Admin-Token": "nope"}).status_code == 401
    ok = client.get("/admin/metrics", headers={"X-Admin-Token": "secret-token"})
    assert ok.status_code == 200
