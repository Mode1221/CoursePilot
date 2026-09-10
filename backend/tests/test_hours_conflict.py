"""수동 편집으로 영업시간 밖에 놓인 자리는 지우지 않고 표시한다."""
from datetime import time

from app.adapters.map_service import MockMapService
from app.pipeline.validation import recompute
from app.schemas import Place, TravelMode


def _place(**kw) -> Place:
    return Place(id="p1", name="장소", category="카페", address="서울", lat=37.54, lng=127.05, **kw)


async def _item(place: Place, start: time):
    items = await recompute([place], start, TravelMode.WALK, MockMapService())
    return items[0]


async def test_브레이크에_걸치면_표시한다():
    place = _place(
        open_time=time(9), close_time=time(21), break_start=time(15), break_end=time(16)
    )
    item = await _item(place, time(14, 50))
    assert item.hours_conflict is True
    assert item.place.id == "p1"  # 지우지는 않는다


async def test_마감을_넘겨_머물면_표시한다():
    item = await _item(_place(open_time=time(9), close_time=time(15)), time(14, 55))
    assert item.hours_conflict is True


async def test_개점_전_도착도_표시한다():
    item = await _item(_place(open_time=time(11), close_time=time(21)), time(9, 0))
    assert item.hours_conflict is True


async def test_영업_중이면_표시하지_않는다():
    item = await _item(_place(open_time=time(9), close_time=time(21)), time(13, 0))
    assert item.hours_conflict is False


async def test_영업시간_정보가_없으면_단정하지_않는다():
    item = await _item(_place(), time(13, 0))
    assert item.hours_conflict is False
