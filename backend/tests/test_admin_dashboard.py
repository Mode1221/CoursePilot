"""운영 대시보드: 지표를 눈으로 볼 수 있어야 한다."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import api

client = TestClient(api)


def test_대시보드_HTML을_준다():
    resp = client.get("/admin/dashboard")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_필요한_항목이_모두_들어_있다():
    html = client.get("/admin/dashboard").text
    for section in ("유료 API", "폴백률", "알림", "학습 신호", "온보딩"):
        assert section in html


def test_집계값을_HTML에_박아_넣지_않는다():
    """데이터는 브라우저가 토큰을 붙여 다시 받는다 — HTML 만으로는 지표가 새지 않는다."""
    from app.metrics import metrics_store

    metrics_store.clear()
    metrics_store.record("GET /secret-route", 200, 5)
    html = client.get("/admin/dashboard").text
    assert "/secret-route" not in html
    metrics_store.clear()


def test_데이터_엔드포인트는_토큰을_본다(monkeypatch):
    import app.config as cfg

    monkeypatch.setattr(cfg.settings, "admin_token", "s3cret")
    assert client.get("/admin/metrics").status_code == 401
    ok = client.get("/admin/metrics", headers={"X-Admin-Token": "s3cret"})
    assert ok.status_code == 200
