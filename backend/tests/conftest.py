"""테스트 격리: 각 테스트 전 rate limit 카운터 초기화.

RateLimitMiddleware는 프로세스 전역 인메모리 카운터(클라이언트 IP별)라, 여러 테스트가
같은 TestClient IP를 공유하면 슬라이딩 윈도우가 누적돼 후속 테스트가 429를 받는다.
"""
import pytest

from app.config import settings
from app.middleware import reset_rate_limits


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    reset_rate_limits()
    yield


@pytest.fixture(autouse=True)
def _paid_mode_by_default(monkeypatch):
    """운영 기본값은 free_mode=True(검증 기간 무료)지만, 크레딧·결제 회귀 테스트는 과금
    경로를 검증해야 하므로 테스트에서는 기본을 False 로 둔다. free_mode 자체는
    test_free_mode.py 에서 명시적으로 켜서 검증한다."""
    monkeypatch.setattr(settings, "free_mode", False)
    yield
