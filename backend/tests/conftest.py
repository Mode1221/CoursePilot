"""테스트 격리: 각 테스트 전 rate limit 카운터 초기화.

RateLimitMiddleware는 프로세스 전역 인메모리 카운터(클라이언트 IP별)라, 여러 테스트가
같은 TestClient IP를 공유하면 슬라이딩 윈도우가 누적돼 후속 테스트가 429를 받는다.
"""
import pytest

from app.middleware import reset_rate_limits


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    reset_rate_limits()
    yield
