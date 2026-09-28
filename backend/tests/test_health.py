"""liveness / readiness 프로브."""
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import api

# `openssl rand -hex 32` 로 만든 것과 같은 모양
STRONG = "9f1c2a7b4e8d0f63a5b1c7e9d2f4a6b80c3e5f7a9b1d3f5e7a9c1b3d5f7e9a1c"


def test_health_is_always_ok():
    """컨테이너 헬스체크가 부르는 곳. 상태 판정은 200 여부로만 한다."""
    with TestClient(api) as client:
        body = client.get("/health").json()
    assert body["status"] == "ok"
    # 어떤 외부 연동이 살아 있는지 한눈에 보이도록 함께 싣는다
    assert body["db"] is False  # 테스트는 인메모리
    assert set(body["integrations"]) >= {"kakao", "naver", "google", "llm", "sms", "payment"}
    assert all(v is False for v in body["integrations"].values())  # 키 없는 환경


def test_readiness_reports_state_in_development():
    # 개발에서는 DB 가 없어도 트래픽을 받는다(인메모리 폴백)
    with TestClient(api) as client:
        res = client.get("/health/ready")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"


def test_readiness_fails_in_production_without_db(monkeypatch):
    # 운영에서 DB 가 안 붙었으면 조용히 인메모리로 돌지 말고 빠져야 한다
    monkeypatch.setattr(settings, "env", "production")
    monkeypatch.setattr(settings, "session_secret", STRONG)
    monkeypatch.setattr(settings, "admin_token", STRONG)
    # 기동 자체를 막지 않도록 개발 기본 비밀번호는 벗어난 값으로
    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://u:pw@db:5432/x")
    with TestClient(api) as client:
        res = client.get("/health/ready")
        assert res.status_code == 503
        assert res.json()["db"] is False


def test_운영_필수_설정이_없으면_기동을_거부한다(monkeypatch):
    """경고만 남기고 뜨면 아무도 안 본다 — 열린 채로 서비스되느니 멈춘다."""
    from app.main import ProductionConfigError

    monkeypatch.setattr(settings, "env", "production")
    monkeypatch.setattr(settings, "session_secret", "")
    monkeypatch.setattr(settings, "admin_token", "")
    with pytest.raises(ProductionConfigError) as exc:
        with TestClient(api):
            pass
    message = str(exc.value)
    assert "SESSION_SECRET" in message and "ADMIN_TOKEN" in message


def test_개발_기본_DB_비밀번호도_미설정으로_본다(monkeypatch):
    from app.main import _production_warnings

    monkeypatch.setattr(settings, "session_secret", STRONG)
    monkeypatch.setattr(settings, "admin_token", STRONG)
    monkeypatch.setattr(
        settings, "database_url", "postgresql+psycopg://coursepilot:coursepilot@db:5432/x"
    )
    assert _production_warnings() == ["POSTGRES_PASSWORD"]


def test_짧거나_예시_같은_시크릿은_없는_것으로_본다(monkeypatch):
    """비어 있지 않아도 'changeme' 같은 값이면 토큰 위조가 쉬워 없는 것과 같다."""
    from app.main import _production_warnings

    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://u:pw@db:5432/x")
    for weak in ("short", "change-me-" + "a" * 30, "my-secret-" + "b" * 30):
        monkeypatch.setattr(settings, "session_secret", weak)
        monkeypatch.setattr(settings, "admin_token", weak)
        assert _production_warnings() == ["SESSION_SECRET", "ADMIN_TOKEN"], weak
    monkeypatch.setattr(settings, "session_secret", STRONG)
    monkeypatch.setattr(settings, "admin_token", STRONG)
    assert _production_warnings() == []
