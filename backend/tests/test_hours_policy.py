"""영업시간 모르는 장소: 덜 알려진 곳은 뒤로, 알려진 곳만 웹검색, 원래 시간 없는 곳은 그대로."""
from datetime import time

import pytest

from app.adapters import hours_fallback
from app.adapters.hours_fallback import fill_missing_hours
from app.pipeline.hours_policy import has_popularity, hours_missing
from app.pipeline.planner import score_place
from app.schemas import Place, PlanConstraints


def _p(pid="p", name="조용한 가게", **kw) -> Place:
    base = {"id": pid, "name": name, "lat": 37.5, "lng": 127.0, "category": "음식점 > 한식"}
    return Place(**{**base, **kw})


def _score(place: Place, popularity: float = 0.0) -> float:
    return score_place(place, PlanConstraints(), None, popularity=popularity)


def test_확인했는데_시간이_없는_무명_장소는_뒤로_간다():
    known = _p(open_time=time(11), close_time=time(21))
    missing = _p(hours_unverified=True)
    assert _score(missing) < _score(known)


def test_아직_안_채운_곳은_감점하지_않는다():
    """배치가 하루 할당량씩 채우는 중 — 인기 있는 곳도 비어 있을 수 있다."""
    unchecked = _p()  # hours_unverified False, open_time None
    known = _p(open_time=time(11), close_time=time(21))
    assert _score(unchecked) == _score(known)


@pytest.mark.parametrize(
    "kw,popularity",
    [
        ({"hot_score": 0.5}, 0.0),
        ({"is_popup": True}, 0.0),
        ({"blog_mentions": 800}, 0.0),
        ({}, 0.3),  # 우리 서비스에서 채택된 곳
    ],
)
def test_인기_신호가_있으면_감점하지_않는다(kw, popularity):
    base = _p(**kw)
    missing = _p(hours_unverified=True, **kw)
    assert _score(missing, popularity) == _score(base, popularity)


def test_공원_거리처럼_원래_시간_없는_곳은_그대로():
    park = _p(name="서울숲", category="여행 > 공원", hours_unverified=True)
    assert not hours_missing(park)
    assert _score(park) == _score(_p(name="서울숲", category="여행 > 공원"))


def test_인기_판정():
    assert not has_popularity(_p(blog_mentions=50))
    assert has_popularity(_p(blog_mentions=300))


@pytest.fixture()
def key(monkeypatch):
    monkeypatch.setattr("app.config.settings.anthropic_api_key", "k")


async def test_웹검색은_알려진_곳만(monkeypatch, key):
    looked: list[str] = []

    async def fake(place):
        looked.append(place.id)
        return time(11, 0), time(21, 0)

    monkeypatch.setattr(hours_fallback, "_lookup", fake)
    places = [
        _p("unknown", hours_unverified=True, blog_mentions=10),
        _p("hot", hours_unverified=True, hot_score=0.4),
        _p("park", name="뚝섬한강공원", category="공원", hours_unverified=True, blog_mentions=5000),
    ]
    assert await fill_missing_hours(places) == 1
    assert looked == ["hot"]
    assert places[0].open_time is None  # 무명 장소는 "확인 필요" 그대로


async def test_우리_서비스에서_채택된_곳도_찾아본다(monkeypatch, key):
    from app.popularity import popularity_store

    async def fake(place):
        return time(11, 0), time(21, 0)

    monkeypatch.setattr(hours_fallback, "_lookup", fake)
    monkeypatch.setattr(popularity_store, "scores", lambda ids: {i: 0.5 for i in ids})
    assert await fill_missing_hours([_p("adopted", hours_unverified=True)]) == 1
