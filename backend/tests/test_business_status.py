"""영업 상태: 폐업·일시 휴업은 후보와 확정 코스 양쪽에서 뺀다."""
from datetime import time

from app.adapters.google import is_closed_now, is_permanently_closed
from app.adapters.localdata import LocalDataRegistry
from app.adapters.map_service import ClosedFilterMapService, MockMapService
from app.pipeline.agent import _verify_hours
from app.schemas import Place, PlanConstraints, TimelineItem


def _place(pid, status=None) -> Place:
    return Place(id=pid, name=pid, lat=37.5, lng=127.0, business_status=status)


def test_영구폐업과_일시휴업을_구분해_판정한다():
    assert is_permanently_closed(_place("a", "CLOSED_PERMANENTLY"))
    assert not is_permanently_closed(_place("a", "CLOSED_TEMPORARILY"))
    # 추천 관점에서는 둘 다 못 간다
    assert is_closed_now(_place("a", "CLOSED_TEMPORARILY"))
    assert not is_closed_now(_place("a", "OPERATIONAL"))
    assert not is_closed_now(_place("a"))


class _Stub(MockMapService):
    def __init__(self, places):
        self._places = places

    async def search_places(self, region, keywords, limit=10):
        return list(self._places)


async def test_후보_단계에서_휴업_장소를_뺀다(monkeypatch):
    monkeypatch.setattr(
        "app.adapters.localdata.get_localdata_registry", lambda: LocalDataRegistry()
    )
    places = [_place("open", "OPERATIONAL"), _place("shut", "CLOSED_TEMPORARILY")]
    result = await ClosedFilterMapService(_Stub(places)).search_places("성수", [])
    assert [p.id for p in result] == ["open"]


def _item(place: Place) -> TimelineItem:
    return TimelineItem(place=place, arrive=time(12, 0), depart=time(13, 0))


async def test_확정_코스에서도_폐업이_확인되면_뺀다(monkeypatch):
    monkeypatch.setattr("app.adapters.google.refresh_final_hours", _noop)
    timeline = [_item(_place("a", "OPERATIONAL")), _item(_place("b", "CLOSED_PERMANENTLY"))]
    result = await _verify_hours(timeline, PlanConstraints(start_time=time(12, 0)), MockMapService())
    assert [i.place.id for i in result] == ["a"]


async def test_전부_정상이면_그대로_둔다(monkeypatch):
    monkeypatch.setattr("app.adapters.google.refresh_final_hours", _noop)
    timeline = [_item(_place("a", "OPERATIONAL"))]
    result = await _verify_hours(timeline, PlanConstraints(), MockMapService())
    assert result == timeline


async def test_지도_서비스가_없으면_시간_재계산_없이_빼기만_한다(monkeypatch):
    monkeypatch.setattr("app.adapters.google.refresh_final_hours", _noop)
    timeline = [_item(_place("a")), _item(_place("b", "CLOSED_PERMANENTLY"))]
    result = await _verify_hours(timeline)
    assert [i.place.id for i in result] == ["a"]


async def _noop(places):
    return places
