"""rate limit 클라이언트 식별·정리."""
from app.middleware import RateLimitMiddleware


class _Req:
    def __init__(self, headers: dict, host: str | None) -> None:
        self.headers = headers
        self.client = type("C", (), {"host": host})() if host else None


def _mw() -> RateLimitMiddleware:
    return RateLimitMiddleware(app=None)


def test_신뢰하는_프록시_뒤에서는_프록시가_덧붙인_주소를_쓴다():
    """프록시는 실제 접속자를 맨 뒤에 붙인다 — 앞쪽은 클라이언트가 지어낼 수 있다."""
    mw = _mw()
    req = _Req({"X-Forwarded-For": "1.2.3.4, 10.0.0.9"}, "10.0.0.1")
    assert mw._client_key(req) == "10.0.0.9"


def test_신뢰하지_않는_곳의_헤더는_무시한다():
    mw = _mw()
    req = _Req({"X-Forwarded-For": "1.2.3.4"}, "8.8.8.8")
    assert mw._client_key(req) == "8.8.8.8"


def test_헤더가_없으면_소켓_주소를_쓴다():
    assert _mw()._client_key(_Req({}, "9.9.9.9")) == "9.9.9.9"


def test_만료된_항목은_정리된다():
    mw = _mw()
    mw._hits["old"] = __import__("collections").deque([0.0])
    mw._hits["new"] = __import__("collections").deque([10_000.0])
    mw._sweep(now=10_000.0)
    assert "old" not in mw._hits
    assert "new" in mw._hits
