"""영업시간 LLM 웹검색 폴백: 최후 수단, 상한, 항상 '확인 필요'."""
from datetime import time

import pytest

from app.adapters import hours_fallback
from app.adapters.hours_fallback import MAX_LOOKUPS_PER_COURSE, fill_missing_hours, parse_hours
from app.schemas import Place


def _place(pid="p", **kw) -> Place:
    base = {"id": pid, "name": "가게", "lat": 37.5, "lng": 127.0, "hours_unverified": True}
    return Place(**{**base, **kw})


@pytest.mark.parametrize(
    "text,expected",
    [
        ('{"open": "10:00", "close": "22:00"}', (time(10, 0), time(22, 0))),
        ('앞말 {"open": "09:30", "close": "18:00"} 뒷말', (time(9, 30), time(18, 0))),
        ('{"open": null, "close": null}', None),
        ('{"open": "25:00", "close": "22:00"}', None),
        ("JSON 아님", None),
        ('{"open": "10:00"}', None),
        ("", None),
    ],
)
def test_응답_파싱(text, expected):
    assert parse_hours(text) == expected


@pytest.fixture()
def key(monkeypatch):
    monkeypatch.setattr("app.config.settings.anthropic_api_key", "k")


async def test_영업시간을_채우되_확인_필요로_남긴다(monkeypatch, key):
    async def fake(place):
        return time(11, 0), time(21, 0)

    monkeypatch.setattr(hours_fallback, "_lookup", fake)
    place = _place()
    assert await fill_missing_hours([place]) == 1
    assert (place.open_time, place.close_time) == (time(11, 0), time(21, 0))
    assert place.hours_unverified is True  # 웹검색 결과는 확정으로 보지 않는다


async def test_이미_영업시간이_있으면_부르지_않는다(monkeypatch, key):
    called = []

    async def fake(place):
        called.append(place.id)
        return None

    monkeypatch.setattr(hours_fallback, "_lookup", fake)
    known = _place("known", open_time=time(10, 0), hours_unverified=True)
    verified = _place("verified", hours_unverified=False)
    assert await fill_missing_hours([known, verified]) == 0
    assert called == []


async def test_코스당_상한을_넘지_않는다(monkeypatch, key):
    called = []

    async def fake(place):
        called.append(place.id)
        return time(10, 0), time(20, 0)

    monkeypatch.setattr(hours_fallback, "_lookup", fake)
    places = [_place(f"p{i}") for i in range(5)]
    assert await fill_missing_hours(places) == MAX_LOOKUPS_PER_COURSE
    assert len(called) == MAX_LOOKUPS_PER_COURSE


async def test_조회_실패는_무영향(monkeypatch, key):
    async def boom(place):
        raise RuntimeError("timeout")

    monkeypatch.setattr(hours_fallback, "_lookup", boom)
    place = _place()
    assert await fill_missing_hours([place]) == 0
    assert place.open_time is None


async def test_키가_없으면_호출하지_않는다(monkeypatch):
    monkeypatch.setattr("app.config.settings.anthropic_api_key", "")
    called = []

    async def fake(place):
        called.append(place.id)

    monkeypatch.setattr(hours_fallback, "_lookup", fake)
    assert await fill_missing_hours([_place()]) == 0
    assert called == []


async def test_LLM_클라이언트가_없으면_None(monkeypatch):
    monkeypatch.setattr("app.llm_client.get_anthropic_client", lambda: None)
    assert await hours_fallback._lookup(_place()) is None
