"""LOCALDATA 폐업 필터·업력 산출."""
import io
from datetime import date

import pytest

from app.adapters.localdata import LocalDataRegistry, get_localdata_registry
from app.adapters.map_service import ClosedFilterMapService, MockMapService
from app.schemas import Place

CSV = """개방자치단체코드,사업장명,도로명주소,지번주소,영업상태명,상세영업상태명,인허가일자,폐업일자
3040000,성수커피,서울특별시 성동구 아차산로 17,서울특별시 성동구 성수동2가 17,영업/정상,영업,20150301,
3040000,문닫은식당,서울특별시 성동구 아차산로 21,서울특별시 성동구 성수동2가 21,폐업,폐업,20180401,20220501
3040000,같은이름,서울특별시 성동구 왕십리로 10,서울특별시 성동구 행당동 10,영업/정상,영업,20200101,
3150000,같은이름,서울특별시 마포구 양화로 55,서울특별시 마포구 서교동 55,폐업,폐업,20100101,20210101
"""


@pytest.fixture()
def registry():
    reg = LocalDataRegistry()
    reg.load_csv(io.StringIO(CSV), loaded_on=date(2026, 1, 1))
    return reg


def test_폐업_업소를_식별한다(registry):
    assert registry.is_closed("문닫은식당", "서울특별시 성동구 아차산로 21")
    assert not registry.is_closed("성수커피", "서울특별시 성동구 아차산로 17")


def test_인허가일자로_업력을_얻는다(registry):
    assert registry.opened_on("성수커피", "서울특별시 성동구 아차산로 17") == date(2015, 3, 1)


def test_상호_표기_차이를_흡수한다(registry):
    assert registry.opened_on("성수 커피 성수점", "서울특별시 성동구 아차산로 17") == date(2015, 3, 1)


def test_동명업소는_주소로_구분한다(registry):
    assert not registry.is_closed("같은이름", "서울특별시 성동구 왕십리로 10")
    assert registry.is_closed("같은이름", "서울특별시 마포구 양화로 55")


def test_주소를_모르는_동명업소는_판단하지_않는다(registry):
    assert not registry.is_closed("같은이름")


def test_대장에_없으면_무판정(registry):
    assert not registry.is_closed("모르는가게", "서울특별시 성동구 어딘가 1")
    assert registry.opened_on("모르는가게") is None


def test_표본이_적으면_폐업률은_None(registry):
    assert registry.closure_rate("서울특별시 성동구 아차산로") is None


def test_주_1회_갱신_기준으로_stale(registry):
    assert not registry.is_stale(date(2026, 1, 6))
    assert registry.is_stale(date(2026, 1, 8))


def test_빈_레지스트리는_항상_stale():
    assert LocalDataRegistry().is_stale()


class _Stub(MockMapService):
    def __init__(self, places):
        self._places = places

    async def search_places(self, region, keywords, limit=10):
        return list(self._places)


async def test_검색결과에서_폐업을_제거하고_업력을_붙인다(monkeypatch, registry):
    monkeypatch.setattr(
        "app.adapters.localdata.get_localdata_registry", lambda: registry
    )
    places = [
        Place(id="a", name="성수커피", address="서울특별시 성동구 아차산로 17", lat=37.5, lng=127.0),
        Place(id="b", name="문닫은식당", address="서울특별시 성동구 아차산로 21", lat=37.5, lng=127.0),
    ]
    result = await ClosedFilterMapService(_Stub(places)).search_places("성수", [])
    assert [p.id for p in result] == ["a"]
    assert result[0].opened_on == date(2015, 3, 1)


async def test_대장이_비면_아무것도_거르지_않는다(monkeypatch):
    monkeypatch.setattr(
        "app.adapters.localdata.get_localdata_registry", lambda: LocalDataRegistry()
    )
    places = [Place(id="b", name="문닫은식당", address="서울특별시 성동구 아차산로 21", lat=37.5, lng=127.0)]
    result = await ClosedFilterMapService(_Stub(places)).search_places("성수", [])
    assert [p.id for p in result] == ["b"]


def test_설정이_없으면_적재하지_않는다():
    get_localdata_registry.cache_clear()
    assert not get_localdata_registry().loaded
    get_localdata_registry.cache_clear()


def test_지번주소만_있어도_대조한다():
    """신원천 헤더에는 "도로명전체주소"가 없다 — 도로명주소/지번주소를 쓴다."""
    reg = LocalDataRegistry()
    reg.load_csv(
        io.StringIO(
            "개방자치단체코드,사업장명,도로명주소,지번주소,영업상태명,상세영업상태명,"
            "인허가일자,폐업일자\n"
            "3040000,지번만,,서울특별시 성동구 성수동2가 333,폐업,폐업,20100101,20200101\n"
        )
    )
    assert reg.is_closed("지번만", "서울특별시 성동구 성수동2가 333") is True


def test_휴업도_영업하지_않는_것으로_본다():
    """당장 갈 수 없는 곳은 코스에 넣지 않는다."""
    reg = LocalDataRegistry()
    reg.load_csv(
        io.StringIO(
            "개방자치단체코드,사업장명,도로명주소,지번주소,영업상태명,상세영업상태명,"
            "인허가일자,폐업일자\n"
            "3040000,쉬는집,서울특별시 성동구 아차산로 99,,영업/정상,휴업,20100101,\n"
        )
    )
    assert reg.is_closed("쉬는집") is True


def test_검색_경로에서는_적재하지_않는다(monkeypatch):
    """요청 경로에서 reload_if_stale 을 부르면 첫 사용자가 수십 초를 기다리고,
    적재 중인 인덱스까지 비워진다. 비어 있으면 그냥 필터 없이 통과한다."""
    import inspect

    from app.adapters import map_service

    source = inspect.getsource(map_service.ClosedFilterMapService)
    assert "reload_if_stale" not in source


def test_대상_시군구_목록에_시도가_붙어_있다():
    from app.adapters.localdata import TARGET_AREAS

    assert ("서울특별시", "성동구") in TARGET_AREAS
    assert ("경기도", "분당구") in TARGET_AREAS
