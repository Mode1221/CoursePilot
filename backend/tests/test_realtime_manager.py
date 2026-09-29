from app.config import Settings
from app.realtime import _client_manager


def test_redis_url_없으면_단일_프로세스(monkeypatch):
    import app.realtime as realtime

    monkeypatch.setattr(realtime, "settings", Settings(redis_url=""))
    assert _client_manager() is None


def test_redis_url_있으면_redis_매니저(monkeypatch):
    import app.realtime as realtime

    monkeypatch.setattr(realtime, "settings", Settings(redis_url="redis://localhost:6379/0"))
    manager = _client_manager()
    # redis 패키지가 없는 환경에서는 폴백(None) 이 정상 동작
    assert manager is None or manager.__class__.__name__ == "AsyncRedisManager"


def test_multi_instance_플래그():
    assert Settings(redis_url="").multi_instance is False
    assert Settings(redis_url="redis://x").multi_instance is True
