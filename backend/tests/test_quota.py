"""월 무료 한도: 초과 호출을 아예 막고 사용량을 노출한다."""
from datetime import UTC, datetime

import pytest

from app.adapters.google import GooglePlacesClient
from app.quota import MONTHLY_FREE_LIMITS, WARN_RATIO, QuotaStore, quota_store

JAN = datetime(2026, 1, 15, tzinfo=UTC)
FEB = datetime(2026, 2, 1, tzinfo=UTC)


@pytest.fixture()
def store():
    return QuotaStore()


def test_한도를_모르는_API는_무제한(store):
    assert store.limit("kakao.search") is None
    assert store.remaining("kakao.search") is None
    assert store.allow("kakao.search")


def test_사용량이_한도에_닿으면_거절한다(store):
    for _ in range(MONTHLY_FREE_LIMITS["google.rating"]):
        assert store.allow("google.rating")
        store.record("google.rating")
    assert not store.allow("google.rating")
    assert store.remaining("google.rating") == 0


def test_달이_바뀌면_다시_센다(store):
    store.record("google.hours", 5_000, now=JAN)
    assert not store.allow("google.hours", now=JAN)
    assert store.allow("google.hours", now=FEB)
    assert store.used("google.hours", now=FEB) == 0


def test_80퍼센트를_넘으면_경고한다(store):
    limit = MONTHLY_FREE_LIMITS["google.hours"]
    store.record("google.hours", int(limit * WARN_RATIO) - 1)
    assert store.alerts() == []
    store.record("google.hours", 2)
    assert [a["target"] for a in store.alerts()] == ["google.hours"]


def test_스냅샷은_한도와_잔여를_보여준다(store):
    store.record("google.rating", 100)
    row = next(r for r in store.snapshot() if r["name"] == "google.rating")
    assert row["used"] == 100 and row["remaining"] == 900 and row["ratio"] == 0.1


class _Client(GooglePlacesClient):
    def __init__(self):
        self._key = "k"


async def test_한도가_소진되면_구글을_호출하지_않는다(monkeypatch):
    quota_store.clear()
    quota_store.record("google.hours", MONTHLY_FREE_LIMITS["google.hours"])
    called = []

    class _Boom:
        async def get(self, *a, **kw):
            called.append(a)
            raise AssertionError("한도를 넘겨 호출하면 안 된다")

    client = _Client()
    client._client = _Boom()
    assert await client.fetch_hours("gp-1") is None
    assert called == []
    quota_store.clear()


async def test_한도_안이면_호출하고_사용량이_는다(monkeypatch):
    quota_store.clear()

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"businessStatus": "OPERATIONAL"}

    class _Ok:
        async def get(self, *a, **kw):
            return _Resp()

    client = _Client()
    client._client = _Ok()
    assert await client.fetch_hours("gp-1") == {"businessStatus": "OPERATIONAL"}
    assert quota_store.used("google.hours") == 1
    quota_store.clear()


def test_임계를_처음_넘을_때만_알린다(monkeypatch, store):
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr("app.quota._notify", lambda kind, target, text: sent.append((kind, text)))
    limit = MONTHLY_FREE_LIMITS["google.rating"]
    store.record("google.rating", int(limit * 0.79))
    assert sent == []
    store.record("google.rating", int(limit * 0.02))  # 80% 진입
    assert len(sent) == 1 and "한도 8" in sent[0][1]
    store.record("google.rating", 1)  # 여전히 80%대 — 다시 알리지 않는다
    assert len(sent) == 1


def test_한도_소진은_따로_알린다(monkeypatch, store):
    sent: list[str] = []
    monkeypatch.setattr("app.quota._notify", lambda kind, target, text: sent.append(text))
    store.record("google.rating", MONTHLY_FREE_LIMITS["google.rating"])
    assert any("소진" in t for t in sent)


def test_달이_바뀌면_다시_알린다(monkeypatch, store):
    sent: list[str] = []
    monkeypatch.setattr("app.quota._notify", lambda kind, target, text: sent.append(text))
    store.record("google.hours", MONTHLY_FREE_LIMITS["google.hours"], now=JAN)
    before = len(sent)
    store.record("google.hours", MONTHLY_FREE_LIMITS["google.hours"], now=FEB)
    assert len(sent) > before


def test_한도가_없는_API는_알리지_않는다(monkeypatch, store):
    sent: list[str] = []
    monkeypatch.setattr("app.quota._notify", lambda kind, target, text: sent.append(text))
    store.record("kakao.search", 1_000_000)
    assert sent == []
