from fastapi.testclient import TestClient

import app.main as main
from app.config import Settings

client = TestClient(main.app)

ADMIN_PATHS = ["/admin/metrics", "/admin/signals"]


def test_토큰_미설정이면_열려있다():
    for path in ADMIN_PATHS:
        assert client.get(path).status_code == 200


def test_토큰이_설정되면_헤더가_필요하다(monkeypatch):
    monkeypatch.setattr(main, "settings", Settings(admin_token="s3cret"))
    for path in ADMIN_PATHS:
        assert client.get(path).status_code == 401
        assert client.get(path, headers={"X-Admin-Token": "wrong"}).status_code == 401
        assert client.get(path, headers={"X-Admin-Token": "s3cret"}).status_code == 200
