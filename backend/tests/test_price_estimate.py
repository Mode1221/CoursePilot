"""1인 비용 추정: 검색 API 가 가격을 주지 않아 예산 조건이 무력해지는 문제."""
import pytest

from app.adapters.localdata import LocalDataRegistry
from app.adapters.map_service import ClosedFilterMapService, MockMapService
from app.pipeline.price_estimate import (
    SLOT_PRICES,
    estimate_price,
    fill_estimated_prices,
)
from app.schemas import Place


def _place(category=None, name="가게", price=None) -> Place:
    return Place(id="p", name=name, category=category, lat=37.5, lng=127.0, price=price)


@pytest.mark.parametrize(
    "category,expected",
    [
        ("음식점 > 한식 > 육류,고기", 25_000),
        ("음식점 > 일식 > 스시", 40_000),
        ("음식점 > 분식", 8_000),
        ("음식점 > 카페 > 디저트", 9_000),
        ("문화,예술 > 전시관", 15_000),
        ("여행 > 공원", 0),
    ],
)
def test_카테고리로_1인_비용을_추정한다(category, expected):
    assert estimate_price(_place(category)) == expected


def test_세부_표기가_없으면_슬롯_기본값을_쓴다():
    assert estimate_price(_place("음식점")) == SLOT_PRICES["meal"]


def test_실제_가격이_있으면_덮어쓰지_않는다():
    place = _place("음식점 > 한식", price=12_345)
    fill_estimated_prices([place])
    assert place.price == 12_345 and place.price_estimated is False


def test_추정값에는_추정_표시가_붙는다():
    place = _place("음식점 > 한식")
    fill_estimated_prices([place])
    assert place.price == 15_000 and place.price_estimated is True


def test_공원은_0원도_추정값으로_인정한다():
    place = _place("여행 > 공원")
    fill_estimated_prices([place])
    assert place.price == 0 and place.price_estimated is True


class _Stub(MockMapService):
    def __init__(self, places):
        self._places = places

    async def search_places(self, region, keywords, limit=10):
        return list(self._places)


async def test_검색_결과에_추정가가_채워진다(monkeypatch):
    monkeypatch.setattr(
        "app.adapters.localdata.get_localdata_registry", lambda: LocalDataRegistry()
    )
    places = [_place("음식점 > 한식 > 육류,고기")]
    result = await ClosedFilterMapService(_Stub(places)).search_places("성수", [])
    assert result[0].price == 25_000 and result[0].price_estimated
