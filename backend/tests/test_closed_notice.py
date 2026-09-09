"""폐업·휴무로 자리가 빠지면 개수 판단과 안내가 함께 바뀌어야 한다."""
from datetime import time

import pytest

from app.main import _ai_reply
from app.pipeline.agent import PlanResult, generate_course
from app.schemas import Course, Place, PlanConstraints, TimelineItem


def _course(n: int) -> Course:
    items = [
        TimelineItem(
            place=Place(id=f"p{i}", name=f"장소{i}", lat=37.5, lng=127.0),
            arrive=time(12 + i, 0),
            depart=time(13 + i, 0),
        )
        for i in range(n)
    ]
    return Course(id="c", items=items)


def test_뺀_자리를_안내한다():
    text = _ai_reply(_course(3), False, False, closed_dropped=2)
    assert "문 닫는 곳 2곳은 빼고" in text


def test_뺀_게_없으면_언급하지_않는다():
    assert "문 닫는 곳" not in _ai_reply(_course(3), False, False)


def test_부족_안내에도_이유를_붙인다():
    text = _ai_reply(_course(2), False, True, closed_dropped=1)
    assert "2곳까지만 찾았어요" in text and "문 닫는 곳 1곳" in text


class _ClosingMap:
    """모든 후보를 정상으로 주지만, 확정 후 검증에서 한 곳이 휴무로 드러난다."""

    def __init__(self):
        from app.adapters.map_service import MockMapService

        self._inner = MockMapService()

    async def search_places(self, region, keywords, limit=10):
        return await self._inner.search_places(region, keywords, limit)

    async def get_route(self, origin, dest, mode):
        return await self._inner.get_route(origin, dest, mode)


@pytest.fixture()
def close_one(monkeypatch):
    async def fake_refresh(places, *, weekday=None):
        if places:
            places[0].closed_that_day = True
        return places

    monkeypatch.setattr("app.adapters.google.refresh_final_hours", fake_refresh)


async def test_확정_후_휴무가_드러나면_개수와_리포트가_함께_줄어든다(close_one):
    result = await generate_course("성수동에서 저녁 코스", _ClosingMap())
    assert isinstance(result, PlanResult)
    assert result.closed_dropped == 1
    assert all(not it.place.closed_that_day for it in result.timeline)


async def test_남은_개수로_확인_필요를_판단한다(close_one, monkeypatch):
    monkeypatch.setattr("app.pipeline.agent._min_usable", lambda c: 4)
    result = await generate_course("성수동에서 저녁 코스", _ClosingMap())
    if len(result.timeline) < 4:
        assert result.needs_confirmation


def test_계획_제약은_그대로_돌려준다():
    assert PlanResult(PlanConstraints(), [], relaxed=False, needs_confirmation=False).closed_dropped == 0
