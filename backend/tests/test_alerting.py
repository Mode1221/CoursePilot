"""임계 알림 웹훅 발송."""
from __future__ import annotations

import pytest

from app.alerting import AlertNotifier
from app.config import settings
from app.metrics import FALLBACK_RATE_ALERT, MIN_ALERT_SAMPLES, metrics_store


@pytest.fixture(autouse=True)
def _clean():
    metrics_store.clear()
    yield
    metrics_store.clear()


async def test_웹훅_미설정이면_발송하지_않는다(monkeypatch):
    monkeypatch.setattr(settings, "alert_webhook_url", "")
    assert await AlertNotifier().send("fallback_rate", "naver", "테스트") is False


async def test_웹훅이_있으면_POST_한다(monkeypatch):
    monkeypatch.setattr(settings, "alert_webhook_url", "https://hook.example/x")
    sent: list[dict] = []

    class _Resp:
        def raise_for_status(self):
            return None

    class _Client:
        def __init__(self, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json):
            sent.append({"url": url, "json": json})
            return _Resp()

    monkeypatch.setattr("httpx.AsyncClient", _Client)
    ok = await AlertNotifier().send("fallback_rate", "naver", "폴백률 60%")
    assert ok is True
    assert sent[0]["url"] == "https://hook.example/x"
    assert sent[0]["json"]["target"] == "naver"


async def test_같은_항목은_재알림_간격_동안_억제된다(monkeypatch):
    monkeypatch.setattr(settings, "alert_webhook_url", "")
    n = AlertNotifier()
    assert n._throttled("fallback_rate:naver") is False
    assert n._throttled("fallback_rate:naver") is True
    assert n._throttled("fallback_rate:google") is False


async def test_발송_실패는_삼킨다(monkeypatch):
    monkeypatch.setattr(settings, "alert_webhook_url", "https://hook.example/x")

    class _Boom:
        def __init__(self, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **kw):
            raise RuntimeError("network down")

    monkeypatch.setattr("httpx.AsyncClient", _Boom)
    assert await AlertNotifier().send("fallback_rate", "naver", "x") is False


async def test_임계_진입시_알림이_트리거된다(monkeypatch):
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "app.alerting.alert_notifier.notify",
        lambda kind, target, text: calls.append((kind, target)),
    )
    for _ in range(MIN_ALERT_SAMPLES):
        metrics_store.record_external("naver.search", ok=False)
    assert ("fallback_rate", "naver.search") in calls

    # 성공을 충분히 쌓아 임계 아래로 내려가면 회복 알림
    for _ in range(MIN_ALERT_SAMPLES * 3):
        metrics_store.record_external("naver.search", ok=True)
    assert FALLBACK_RATE_ALERT > 0
    assert ("fallback_recovered", "naver.search") in calls
