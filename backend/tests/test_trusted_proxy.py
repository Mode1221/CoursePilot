"""프록시 뒤에서의 rate limit 기준 주소.

Caddy 뒤에서는 소켓 주소가 전부 프록시라, 그대로 쓰면 한 사람이 제한을 채우면
모두가 막힌다. 반대로 헤더를 무조건 믿으면 아무나 우회한다.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware import RateLimitMiddleware, is_trusted_proxy, reset_rate_limits


def _client(limit: int = 3, peer: str = "127.0.0.1") -> TestClient:
    """peer 는 백엔드가 보는 소켓 주소(= 프록시 또는 직접 접속자)."""
    return TestClient(_app(limit), client=(peer, 51234))


def _app(limit: int = 3):
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, limit=limit, window_sec=60)

    @app.get("/ping")
    def ping():
        return {"ok": True}

    return app


@pytest.fixture(autouse=True)
def _reset():
    reset_rate_limits()
    yield
    reset_rate_limits()


@pytest.mark.parametrize(
    "host,trusted",
    [("127.0.0.1", True), ("172.18.0.5", True), ("10.1.2.3", True),
     ("192.168.1.7", True), ("8.8.8.8", False), ("garbage", False)],
)
def test_사설망만_프록시로_신뢰한다(host, trusted):
    assert is_trusted_proxy(host) is trusted


def test_프록시_뒤에서는_사용자별로_따로_센다():
    client = _client(limit=2, peer="172.18.0.9")  # 도커 브리지에서 온 Caddy
    for _ in range(2):
        assert client.get("/ping", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200
    assert client.get("/ping", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 429
    # 다른 사용자는 영향을 받지 않아야 한다
    assert client.get("/ping", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 200


def test_신뢰하지_않는_곳에서_온_헤더는_무시한다():
    """프록시를 거치지 않은 직접 접속은 헤더로 IP 를 갈아탈 수 없다."""
    client = _client(limit=2, peer="8.8.8.8")
    for i in range(2):
        assert client.get("/ping", headers={"X-Forwarded-For": f"5.5.5.{i}"}).status_code == 200
    assert client.get("/ping", headers={"X-Forwarded-For": "5.5.5.99"}).status_code == 429


def test_앞쪽_항목을_지어내도_우회할_수_없다():
    """프록시는 실제 접속자를 맨 뒤에 덧붙인다 — 왼쪽은 클라이언트가 지어낸 값이다."""
    client = _client(limit=2, peer="172.18.0.9")
    for i in range(2):
        res = client.get("/ping", headers={"X-Forwarded-For": f"9.9.9.{i}, 3.3.3.3"})
        assert res.status_code == 200
    res = client.get("/ping", headers={"X-Forwarded-For": "9.9.9.99, 3.3.3.3"})
    assert res.status_code == 429  # 맨 오른쪽(3.3.3.3)이 기준이라 우회되지 않는다
