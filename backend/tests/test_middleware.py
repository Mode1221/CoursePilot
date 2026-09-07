from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware import RateLimitMiddleware


def _app(limit: int):
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, limit=limit, window_sec=60)

    @app.get("/ping")
    def ping():
        return {"ok": True}

    return app


def test_rate_limit_blocks_after_limit():
    client = TestClient(_app(limit=2))
    assert client.get("/ping").status_code == 200
    assert client.get("/ping").status_code == 200
    res = client.get("/ping")
    assert res.status_code == 429
    assert "Retry-After" in res.headers


def test_health_is_exempt():
    app = _app(limit=1)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    client = TestClient(app)
    client.get("/health")
    # 헬스체크는 카운트에 포함되지 않아 계속 200
    assert client.get("/health").status_code == 200
