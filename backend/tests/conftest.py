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


@pytest.fixture(autouse=True)
def _isolated_place_repo():
    """저장 장소는 코스 후보 풀로 쓰인다 — 앞 테스트가 남긴 목업 장소가 다음 테스트 코스에
    섞이지 않도록 테스트마다 인메모리 저장소를 비운다."""
    from app.pipeline.stored_pool import clear_cache
    from app.places import place_repo

    place_repo._mem.clear()
    clear_cache()
    yield
    place_repo._mem.clear()
    clear_cache()


@pytest.fixture(autouse=True)
def _reset_sms_ip_caps():
    """IP 당 하루 문자 상한은 테스트 클라이언트 주소 하나로 누적된다 — 테스트마다 비운다."""
    from app.auth import verification_store

    verification_store._ip_sends.clear()
    yield


@pytest.fixture(autouse=True)
def _fresh_map_service():
    """지도 서비스는 벤더 키가 있으면 재사용된다 — 테스트끼리 설정이 새지 않게 비운다."""
    import app.adapters.map_service as ms

    ms._SERVICE = None
    yield
    ms._SERVICE = None


@pytest.fixture(autouse=True)
def _reset_usage_counters():
    """사용 한도 카운터(체험·회원·서비스 전체)는 프로세스 전역이다 — 테스트마다 비운다."""
    from app import usage

    usage.counters.clear()
    usage._warned.clear()
    yield
    usage.counters.clear()
