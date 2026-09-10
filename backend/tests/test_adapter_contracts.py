"""벤더 응답 계약 테스트.

실호출 검증은 키가 있어야 하지만, "응답이 이 모양일 때 우리 코드가 제대로
읽는가"는 지금 확인할 수 있다. 각 벤더 문서의 실제 응답 형태를 픽스처로 두고
파싱·정규화를 고정한다. 필드명이 바뀌거나 우리가 잘못 읽으면 여기서 깨진다.
"""
from __future__ import annotations

import json
from datetime import date, time
from pathlib import Path

import httpx
import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def text(name: str) -> str:
    return (FIXTURES / name).read_text()


class _Stub(httpx.AsyncBaseTransport):
    """정해진 응답만 돌려주는 전송 계층(네트워크 없이 어댑터를 그대로 돌린다)."""

    def __init__(self, payload=None, *, body: str | None = None, status: int = 200):
        self._payload, self._body, self._status = payload, body, status

    async def handle_async_request(self, request):
        if self._body is not None:
            return httpx.Response(self._status, text=self._body)
        return httpx.Response(self._status, json=self._payload)


def _client(payload=None, *, body: str | None = None, status: int = 200) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=_Stub(payload, body=body, status=status))


# ── 카카오 로컬 ────────────────────────────────────────────────
async def test_카카오_키워드_응답을_정규화한다():
    from app.adapters.kakao import KakaoLocalService

    service = KakaoLocalService()
    service._client = _client(load("kakao_keyword.json"))
    docs = await service._keyword_page("성수 카페", 1)
    from app.adapters.kakao import to_place

    places = [to_place(d) for d in docs]
    assert [p.id for p in places] == ["kakao-26338954", "kakao-12345678"]
    assert places[0].category_code == "CE7"
    assert (places[0].lat, places[0].lng) == (37.5445, 127.0557)
    assert places[0].address == "서울 성동구 아차산로 17"


async def test_카카오_카테고리_응답으로_상권을_수집한다():
    from app.adapters.kakao import KakaoLocalService

    service = KakaoLocalService()
    service._client = _client(load("kakao_category.json"))
    places = await service.search_category("FD6", 37.5445, 127.0557, pages=1)
    assert [p.name for p in places] == ["성수식당"]


async def test_카카오_세부_카테고리로_술집을_가른다():
    from app.adapters.kakao import slot_for, to_place

    docs = load("kakao_keyword.json")["documents"]
    slots = [slot_for(p.category_code, p.category) for p in map(to_place, docs)]
    assert slots == ["cafe", "bar"]


# ── 네이버 지역검색 / 경로 ─────────────────────────────────────
async def test_네이버_지역검색_응답을_정규화한다():
    from app.adapters.naver import NaverMapService

    service = NaverMapService()
    service._client = _client(load("naver_local_search.json"))
    places = await service.search_places("성수", ["카페"], limit=5)
    # 좌표가 0인 항목은 버린다(코스에 넣으면 동선이 망가진다)
    assert [p.name for p in places] == ["성수 커피"]
    assert (places[0].lat, places[0].lng) == (37.5445, 127.0557)


async def test_네이버_경로_응답을_분으로_바꾼다():
    from app.adapters.naver import NaverMapService
    from app.quota import quota_store
    from app.schemas import Place, TravelMode

    quota_store.clear()
    service = NaverMapService()
    service._client = _client(load("naver_directions.json"))
    a = Place(id="a", name="a", lat=37.5445, lng=127.0557)
    b = Place(id="b", name="b", lat=37.4979, lng=127.0276)
    route = await service.get_route(a, b, TravelMode.CAR)
    assert route.duration_min == 23  # 1,380,000ms = 23분
    assert route.distance_m == 8200
    quota_store.clear()


async def test_네이버_경로가_없으면_근사로_떨어진다():
    from app.adapters.naver import NaverMapService
    from app.quota import quota_store
    from app.schemas import Place, TravelMode

    quota_store.clear()
    service = NaverMapService()
    service._client = _client(load("naver_directions_no_route.json"))
    a = Place(id="a", name="a", lat=37.5445, lng=127.0557)
    b = Place(id="b", name="b", lat=37.4979, lng=127.0276)
    route = await service.get_route(a, b, TravelMode.CAR)
    assert route.duration_min > 0  # 예외 대신 근사값
    quota_store.clear()


# ── Google Places v1 ──────────────────────────────────────────
async def test_구글_IDs_only_응답에서_place_id를_얻는다():
    from app.adapters.google import GooglePlacesClient
    from app.schemas import Place

    client = GooglePlacesClient()
    client._key = "k"
    client._client = _client(load("google_text_search_ids.json"))
    place_id = await client.map_place_id(Place(id="p", name="성수커피", lat=37.5, lng=127.0))
    assert place_id == "ChIJN1t_tDeuEmsRUsoyG83frY4"


async def test_구글_영업시간_응답을_읽는다():
    from app.adapters.google import _weekday_break, _weekday_period

    hours = load("google_place_hours.json")["regularOpeningHours"]
    assert _weekday_period(hours, 0) == (time(11, 0), time(22, 0))
    assert _weekday_break(hours, 0) == (time(15, 0), time(17, 0))
    # 구간이 하나뿐인 요일은 브레이크가 없다
    assert _weekday_break(hours, 1) == (None, None)


async def test_구글_평점_응답은_표본과_함께_온다():
    from app.adapters.google import GooglePlacesClient

    client = GooglePlacesClient()
    client._key = "k"
    client._client = _client(load("google_place_rating.json"))
    assert await client.fetch_rating("gp-1") == (4.3, 812)


# ── TourAPI ───────────────────────────────────────────────────
async def test_투어API_소개정보에서_이용시간을_읽는다():
    from app.adapters.tourapi import TourApiClient

    client = TourApiClient()
    client._key = "k"
    client._client = _client(load("tourapi_intro.json"))
    intro = await client.intro("126508", "14")
    from app.adapters.tourapi import parse_break, parse_hours

    assert parse_hours(intro["usetimeculture"]) == ("09:00", "18:00")
    assert parse_break(intro["usetimeculture"]) == ("12:00", "13:00")


async def test_투어API_단건_응답도_목록으로_읽는다():
    from app.adapters.tourapi import TourApiClient

    client = TourApiClient()
    client._key = "k"
    client._client = _client(load("tourapi_search.json"))
    item = await client.find("서울숲")
    assert item["title"] == "서울숲"


async def test_투어API_빈_응답은_None():
    from app.adapters.tourapi import TourApiClient

    client = TourApiClient()
    client._key = "k"
    client._client = _client(load("tourapi_empty.json"))
    assert await client.find("없는 곳") is None


# ── KOPIS ─────────────────────────────────────────────────────
async def test_KOPIS_XML을_공연으로_읽는다():
    from app.adapters.culture import CultureClient

    client = CultureClient()
    client._key = "k"
    client._client = _client(body=text("kopis_performances.xml"))
    found = await client.performances(date(2026, 9, 10))
    assert [p.title for p in found] == ["성수 사진전"]
    assert found[0].venue == "성수아트홀"
    assert found[0].end == date(2026, 10, 31)


# ── LOCALDATA CSV ─────────────────────────────────────────────
def test_LOCALDATA_표준_컬럼을_읽는다():
    from app.adapters.localdata import LocalDataRegistry

    registry = LocalDataRegistry()
    assert registry.load_csv(text("localdata_sample.csv")) == 2
    assert registry.opened_on("성수커피", "서울특별시 성동구 아차산로 17") == date(2015, 3, 1)
    assert registry.is_closed("문닫은식당", "서울특별시 성동구 아차산로 21")


@pytest.mark.parametrize(
    "name",
    [
        "kakao_keyword.json",
        "kakao_category.json",
        "naver_local_search.json",
        "naver_directions.json",
        "google_place_hours.json",
        "tourapi_intro.json",
    ],
)
def test_픽스처는_유효한_JSON이다(name):
    assert load(name)


async def test_네이버_대체_경로_키도_읽는다():
    """traoptimal 이 없고 trafast 만 오는 응답도 있다."""
    from app.adapters.naver import _route_summary

    body = {"route": {"trafast": [{"summary": {"distance": 100, "duration": 60000}}]}}
    assert _route_summary(body)["distance"] == 100
    assert _route_summary({"code": 1}) is None
    assert _route_summary({}) is None
