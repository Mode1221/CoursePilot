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
    for _ in range(MONTHLY_FREE_LIMITS["google.details"]):
        assert store.allow("google.details")
        store.record("google.details")
    assert not store.allow("google.details")
    assert store.remaining("google.details") == 0


def test_달이_바뀌면_다시_센다(store):
    store.record("google.details", 5_000, now=JAN)
    assert not store.allow("google.details", now=JAN)
    assert store.allow("google.details", now=FEB)
    assert store.used("google.details", now=FEB) == 0


def test_80퍼센트를_넘으면_경고한다(store):
    limit = MONTHLY_FREE_LIMITS["google.details"]
    store.record("google.details", int(limit * WARN_RATIO) - 1)
    assert store.alerts() == []
    store.record("google.details", 2)
    assert [a["target"] for a in store.alerts()] == ["google.details"]


def test_스냅샷은_한도와_잔여를_보여준다(store):
    store.record("google.details", 100)
    row = next(r for r in store.snapshot() if r["name"] == "google.details")
    assert row["used"] == 100 and row["remaining"] == 900 and row["ratio"] == 0.1


class _Client(GooglePlacesClient):
    def __init__(self):
        self._key = "k"


async def test_한도가_소진되면_구글을_호출하지_않는다(monkeypatch):
    quota_store.clear()
    quota_store.record("google.details", MONTHLY_FREE_LIMITS["google.details"])
    called = []

    class _Boom:
        async def get(self, *a, **kw):
            called.append(a)
            raise AssertionError("한도를 넘겨 호출하면 안 된다")

    client = _Client()
    client._client = _Boom()
    assert await client.fetch_details("gp-1") is None
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
    assert await client.fetch_details("gp-1") == {"businessStatus": "OPERATIONAL"}
    assert quota_store.used("google.details") == 1
    quota_store.clear()


def test_임계를_처음_넘을_때만_알린다(monkeypatch, store):
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr("app.quota._notify", lambda kind, target, text: sent.append((kind, text)))
    limit = MONTHLY_FREE_LIMITS["google.details"]
    store.record("google.details", int(limit * 0.79))
    assert sent == []
    store.record("google.details", int(limit * 0.02))  # 80% 진입
    assert len(sent) == 1 and "한도 8" in sent[0][1]
    store.record("google.details", 1)  # 여전히 80%대 — 다시 알리지 않는다
    assert len(sent) == 1


def test_한도_소진은_따로_알린다(monkeypatch, store):
    sent: list[str] = []
    monkeypatch.setattr("app.quota._notify", lambda kind, target, text: sent.append(text))
    store.record("google.details", MONTHLY_FREE_LIMITS["google.details"])
    assert any("소진" in t for t in sent)


def test_달이_바뀌면_다시_알린다(monkeypatch, store):
    sent: list[str] = []
    monkeypatch.setattr("app.quota._notify", lambda kind, target, text: sent.append(text))
    store.record("google.details", MONTHLY_FREE_LIMITS["google.details"], now=JAN)
    before = len(sent)
    store.record("google.details", MONTHLY_FREE_LIMITS["google.details"], now=FEB)
    assert len(sent) > before


def test_한도가_없는_API는_알리지_않는다(monkeypatch, store):
    sent: list[str] = []
    monkeypatch.setattr("app.quota._notify", lambda kind, target, text: sent.append(text))
    store.record("kakao.search", 1_000_000)
    assert sent == []


def test_DB가_있으면_사용량을_영속화한다(monkeypatch, tmp_path):
    """재시작으로 카운터가 되살아나면 무료 한도를 넘겨 과금된다."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.models import Base

    engine = create_engine(f"sqlite:///{tmp_path/'q.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(engine)
    monkeypatch.setattr("app.db.SessionLocal", Session, raising=False)
    monkeypatch.setattr(QuotaStore, "_db_ready", staticmethod(lambda: True))

    store = QuotaStore()
    store.record("google.details", 40)
    assert store.used("google.details") == 40

    # 새 프로세스처럼 완전히 새 인스턴스로 읽어도 사용량이 남아 있어야 한다
    assert QuotaStore().used("google.details") == 40
    assert QuotaStore().remaining("google.details") == MONTHLY_FREE_LIMITS["google.details"] - 40


def test_DB에서도_달이_바뀌면_0부터(monkeypatch, tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.models import Base

    engine = create_engine(f"sqlite:///{tmp_path/'q2.db'}")
    Base.metadata.create_all(engine)
    monkeypatch.setattr("app.db.SessionLocal", sessionmaker(engine), raising=False)
    monkeypatch.setattr(QuotaStore, "_db_ready", staticmethod(lambda: True))

    store = QuotaStore()
    store.record("google.details", 10, now=JAN)
    assert store.used("google.details", now=JAN) == 10
    assert store.used("google.details", now=FEB) == 0


def test_LLM_영업시간_폴백에_일_상한이_있다(monkeypatch):
    """건당 과금이라 코스가 몰리면 월말 전에 요금이 크게 는다. 상한은 설정으로 조절."""
    from app.config import settings
    from app.quota import QuotaStore

    monkeypatch.setattr(settings, "hours_fallback_daily_cap", 10)
    store = QuotaStore()
    limit = store.daily_limit("llm.hours_fallback")
    assert limit == 10
    store.record_today("llm.hours_fallback", limit - 1)
    assert store.allow_today("llm.hours_fallback") is True
    store.record_today("llm.hours_fallback")
    assert store.allow_today("llm.hours_fallback") is False


def test_일_상한은_날짜가_바뀌면_초기화된다():
    from datetime import UTC, datetime

    from app.quota import QuotaStore

    store = QuotaStore()
    day1 = datetime(2026, 9, 21, tzinfo=UTC)
    day2 = datetime(2026, 9, 22, tzinfo=UTC)
    store.record_today("llm.hours_fallback", 50, now=day1)
    assert store.allow_today("llm.hours_fallback", now=day1) is False
    assert store.allow_today("llm.hours_fallback", now=day2) is True


async def test_일_상한을_넘으면_웹검색을_부르지_않는다(monkeypatch):
    from app.adapters.hours_fallback import fill_missing_hours
    from app.quota import DAILY_LIMITS, quota_store
    from app.schemas import Place

    monkeypatch.setattr("app.config.settings.anthropic_api_key", "k")
    quota_store.clear()
    quota_store.record_today("llm.hours_fallback", DAILY_LIMITS["llm.hours_fallback"])
    called = []

    async def _boom(place):
        called.append(place.id)
        raise AssertionError("상한을 넘었는데 호출됐다")

    monkeypatch.setattr("app.adapters.hours_fallback._lookup", _boom)
    place = Place(id="p", name="가게", lat=37.5, lng=127.0, hours_unverified=True)
    assert await fill_missing_hours([place]) == 0
    assert called == []
    quota_store.clear()
