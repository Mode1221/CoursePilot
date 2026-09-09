"""카카오 로컬 어댑터: 정규화, 카테고리 코드 기반 슬롯 분류, 경로 위임."""
import pytest

from app.adapters.kakao import (
    GROUP_CODE_SLOT,
    SLOT_GROUP_CODES,
    KakaoLocalService,
    slot_for,
    to_place,
)
from app.adapters.map_service import MockMapService
from app.pipeline.planner import classify
from app.schemas import Place, TravelMode

DOC = {
    "id": "1234",
    "place_name": "성수 갈비",
    "category_name": "음식점 > 한식 > 육류,고기",
    "category_group_code": "FD6",
    "road_address_name": "서울 성동구 아차산로 17",
    "address_name": "서울 성동구 성수동",
    "x": "127.0557",
    "y": "37.5445",
}


def test_응답을_정규화한다():
    place = to_place(DOC)
    assert place.id == "kakao-1234"
    assert place.name == "성수 갈비"
    assert place.category_code == "FD6"
    assert (place.lat, place.lng) == (37.5445, 127.0557)
    assert place.address == "서울 성동구 아차산로 17"


def test_좌표가_없으면_버린다():
    assert to_place({**DOC, "x": None}) is None
    assert to_place({"place_name": "이름만"}) is None


def test_id가_없으면_이름_주소_해시로_만든다():
    doc = {k: v for k, v in DOC.items() if k != "id"}
    place = to_place(doc)
    assert place.id.startswith("kakao-") and len(place.id) == 18


@pytest.mark.parametrize(
    "code,name,expected",
    [
        ("FD6", "음식점 > 한식", "meal"),
        ("CE7", "음식점 > 카페", "cafe"),
        ("AT4", "여행 > 관광명소", "activity"),
        ("CT1", "문화,예술 > 전시관", "activity"),
        ("FD6", "음식점 > 술집 > 호프", "bar"),
        ("FD6", "음식점 > 술집 > 이자카야", "bar"),
        ("SW8", "교통 > 지하철역", None),
        (None, None, None),
    ],
)
def test_카테고리_코드로_슬롯을_가른다(code, name, expected):
    assert slot_for(code, name) == expected


def test_슬롯_분류가_코드를_우선한다():
    # 이름만 보면 "예술"이 섞여 활동으로 갈 법한 카페도 코드가 있으면 정확히 갈린다
    place = Place(id="p", name="x", category="문화,예술 > 카페", category_code="CE7", lat=37.5, lng=127.0)
    assert classify(place) == "cafe"


def test_코드가_없으면_이름_기반_분류로_돌아간다():
    place = Place(id="p", name="x", category="카페>디저트", lat=37.5, lng=127.0)
    assert classify(place) == "cafe"


def test_배치용_그룹코드_매핑이_슬롯을_모두_덮는다():
    assert set(SLOT_GROUP_CODES) == {"meal", "cafe", "bar", "activity"}
    for codes in SLOT_GROUP_CODES.values():
        assert all(code in GROUP_CODE_SLOT for code in codes)


async def test_검색은_중복을_제거하고_limit을_지킨다(monkeypatch):
    service = KakaoLocalService()
    pages = {1: [DOC, {**DOC, "id": "2"}], 2: [{**DOC, "id": "2"}, {**DOC, "id": "3"}]}

    async def fake_page(query, page, center=None):
        return pages.get(page, [])

    monkeypatch.setattr(service, "_keyword_page", fake_page)
    result = await service.search_places("성수", ["고기"], limit=10)
    assert [p.id for p in result] == ["kakao-1234", "kakao-2"]


async def test_limit에_도달하면_다음_페이지를_부르지_않는다(monkeypatch):
    service = KakaoLocalService()
    seen: list[int] = []

    async def fake_page(query, page, center=None):
        seen.append(page)
        return [{**DOC, "id": f"{page}-{i}"} for i in range(15)]

    monkeypatch.setattr(service, "_keyword_page", fake_page)
    await service.search_places("성수", [], limit=10)
    assert seen == [1, 1]  # 지역 좌표 조회 1회 + 검색 1페이지


async def test_지역_좌표로_반경을_건다(monkeypatch):
    service = KakaoLocalService()
    calls: list[tuple[str, tuple[float, float] | None]] = []

    async def fake_page(query, page, center=None):
        calls.append((query, center))
        return [DOC]

    monkeypatch.setattr(service, "_keyword_page", fake_page)
    await service.search_places("성수", ["고기"], limit=5)
    # 첫 콜은 지역 좌표 조회, 그다음부터는 그 좌표를 반경 기준으로 넘긴다
    assert calls[0] == ("성수", None)
    assert calls[1] == ("성수 고기", (37.5445, 127.0557))


async def test_지역_좌표는_한_번만_조회한다(monkeypatch):
    service = KakaoLocalService()
    lookups: list[str] = []

    async def fake_page(query, page, center=None):
        if center is None:
            lookups.append(query)
        return [DOC]

    monkeypatch.setattr(service, "_keyword_page", fake_page)
    await service.search_places("성수", ["고기"], limit=5)
    await service.search_places("성수", ["카페"], limit=5)
    assert lookups == ["성수"]


async def test_좌표를_못_찾으면_반경_없이_검색한다(monkeypatch):
    service = KakaoLocalService()
    centers: list[tuple[float, float] | None] = []

    async def fake_page(query, page, center=None):
        centers.append(center)
        return [] if query == "없는동네" else [DOC]

    monkeypatch.setattr(service, "_keyword_page", fake_page)
    result = await service.search_places("없는동네", ["고기"], limit=5)
    assert centers[1] is None and [p.id for p in result] == ["kakao-1234"]


async def test_경로는_위임한다():
    service = KakaoLocalService(route_service=MockMapService())
    a = to_place(DOC)
    b = to_place({**DOC, "id": "2", "x": "127.06", "y": "37.55"})
    route = await service.get_route(a, b, TravelMode.WALK)
    assert route.from_place_id == a.id and route.duration_min >= 1


def test_키가_없으면_비활성():
    assert KakaoLocalService().enabled is False
