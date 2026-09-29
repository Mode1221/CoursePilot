"""빠진 자리 되채우기: 폐업·휴무로 줄어든 코스를 한 번만 다시 시도한다."""
import pytest

from app.adapters.map_service import MockMapService
from app.pipeline.agent import generate_course


class _Map(MockMapService):
    """호출할 때마다 다른 장소 묶음을 준다(재시도로 새 후보를 얻도록)."""

    def __init__(self):
        self.searches = 0

    async def search_places(self, region, keywords, limit=10):
        self.searches += 1
        places = await super().search_places(region, keywords, limit)
        if self.searches > 1:  # 재시도에서는 id 를 바꿔 새 후보처럼 보이게 한다
            for p in places:
                p.id = f"{p.id}-r"
        return places


@pytest.fixture()
def drop_first(monkeypatch):
    """첫 번째 장소가 확정 후 휴무로 드러나는 상황."""
    dropped: list[str] = []

    async def fake_refresh(places, *, weekday=None):
        for place in places:
            if not place.id.endswith("-r") and not dropped:
                place.closed_that_day = True
                dropped.append(place.id)
        return places

    monkeypatch.setattr("app.adapters.google.refresh_final_hours", fake_refresh)
    return dropped


async def test_빠진_자리를_다시_채운다(drop_first):
    result = await generate_course("성수동에서 저녁 코스 3곳", _Map())
    assert result.timeline
    assert all(not it.place.closed_that_day for it in result.timeline)


async def test_되채우기는_한_번만_시도한다(monkeypatch, drop_first):
    calls: list[int] = []
    from app.pipeline import agent

    original = agent._attempt

    async def counting(*a, **kw):
        calls.append(1)
        return await original(*a, **kw)

    monkeypatch.setattr(agent, "_attempt", counting)
    await generate_course("성수동에서 저녁 코스 3곳", _Map())
    assert len(calls) <= 4  # 최초 + 완화 재시도들 + 되채우기 1회


async def test_빠진_게_없으면_다시_시도하지_않는다(monkeypatch):
    async def noop(places, *, weekday=None):
        return places

    monkeypatch.setattr("app.adapters.google.refresh_final_hours", noop)
    from app.pipeline import agent

    calls: list[int] = []
    original = agent._attempt

    async def counting(*a, **kw):
        calls.append(1)
        return await original(*a, **kw)

    monkeypatch.setattr(agent, "_attempt", counting)
    result = await generate_course("성수동에서 저녁 코스", _Map())
    assert result.closed_dropped == 0
    assert len(calls) <= 3
