"""장소 DB 구축 배치: 전수 수집·폐업 제거·Google 콜 페이싱."""
from datetime import UTC, date, datetime

import pytest

from app.adapters.google import GooglePlacesClient
from app.adapters.kakao import KakaoLocalService
from app.adapters.localdata import LocalDataRegistry
from app.batch.districts import DISTRICTS
from app.batch.places_build import (
    GROUP_CODES,
    collect,
    drop_closed,
    fill_hours,
    fill_ratings,
    run,
)
from app.schemas import Place

CSV = """사업장명,도로명전체주소,상세영업상태명,인허가일자,폐업일자
살아있는집,서울 성동구 아차산로 17,영업/정상,20150301,
문닫은집,서울 성동구 아차산로 21,폐업,20180401,20220501
"""


def _place(pid: str, name: str = "가게", address: str | None = None) -> Place:
    return Place(id=pid, name=name, address=address, lat=37.5, lng=127.0)


class _FakeKakao(KakaoLocalService):
    def __init__(self, per_call=2, fail_codes=()):
        self.calls: list[tuple[str, float]] = []
        self._per_call = per_call
        self._fail = set(fail_codes)

    async def search_category(self, group_code, lat, lng, radius_m=1000, pages=3):
        self.calls.append((group_code, lat))
        if group_code in self._fail:
            raise RuntimeError("boom")
        return [_place(f"{group_code}-{lat}-{i}") for i in range(self._per_call)]


async def test_상권마다_모든_카테고리를_훑는다():
    kakao = _FakeKakao()
    places = await collect(kakao, DISTRICTS[:2])
    assert len(kakao.calls) == 2 * len(GROUP_CODES)
    assert len(places) == 2 * len(GROUP_CODES) * 2


async def test_한_상권_실패가_배치를_멈추지_않는다():
    places = await collect(_FakeKakao(fail_codes=("FD6",)), DISTRICTS[:1])
    assert places and all(not p.id.startswith("FD6") for p in places)


async def test_중복_장소는_한_번만():
    class _Dup(_FakeKakao):
        async def search_category(self, group_code, lat, lng, radius_m=1000, pages=3):
            return [_place("same")]

    assert len(await collect(_Dup(), DISTRICTS[:3])) == 1


def test_폐업을_빼고_인허가일자를_붙인다(monkeypatch):
    registry = LocalDataRegistry()
    registry.load_csv(CSV)
    monkeypatch.setattr("app.adapters.localdata.get_localdata_registry", lambda: registry)
    places = [
        _place("a", "살아있는집", "서울 성동구 아차산로 17"),
        _place("b", "문닫은집", "서울 성동구 아차산로 21"),
    ]
    kept, removed = drop_closed(places)
    assert [p.id for p in kept] == ["a"] and removed == 1
    assert kept[0].opened_on == date(2015, 3, 1)


def test_대장이_없으면_그대로_통과(monkeypatch):
    monkeypatch.setattr(
        "app.adapters.localdata.get_localdata_registry", lambda: LocalDataRegistry()
    )
    kept, removed = drop_closed([_place("b", "문닫은집")])
    assert len(kept) == 1 and removed == 0


class _FakeGoogle(GooglePlacesClient):
    def __init__(self):
        self._key = "k"
        self.hours: list[str] = []
        self.ratings: list[str] = []

    async def refresh_hours(self, place, weekday=None):
        self.hours.append(place.id)
        place.hours_checked_at = datetime.now(UTC)
        return place

    async def refresh_rating(self, place):
        self.ratings.append(place.id)
        place.rating, place.rating_checked_at = 4.1, datetime.now(UTC)
        return place


async def test_영업시간은_하루_할당량까지만(monkeypatch):
    google = _FakeGoogle()
    monkeypatch.setattr("app.adapters.google.get_places_client", lambda: google)
    filled = await fill_hours([_place(f"p{i}") for i in range(10)], limit=3)
    assert filled == 3 and len(google.hours) == 3


async def test_이미_최신인_영업시간은_묻지_않는다(monkeypatch):
    google = _FakeGoogle()
    monkeypatch.setattr("app.adapters.google.get_places_client", lambda: google)
    fresh = _place("p")
    fresh.hours_checked_at = datetime.now(UTC)
    assert await fill_hours([fresh]) == 0


async def test_평점은_인기_상위에만_묻는다(monkeypatch):
    google = _FakeGoogle()
    monkeypatch.setattr("app.adapters.google.get_places_client", lambda: google)
    monkeypatch.setattr(
        "app.popularity.popularity_store.scores", lambda ids: {"p2": 9.0, "p0": 1.0}
    )
    places = [_place(f"p{i}") for i in range(5)]
    filled = await fill_ratings(places, limit=2, top_per_district=2)
    assert google.ratings == ["p2", "p0"] and filled == 2


async def test_키가_없으면_구글_단계를_건너뛴다(monkeypatch):
    client = GooglePlacesClient()
    client._key = ""
    monkeypatch.setattr("app.adapters.google.get_places_client", lambda: client)
    assert await fill_hours([_place("p")]) == 0
    assert await fill_ratings([_place("p")]) == 0


@pytest.mark.parametrize("hours_limit", [0, 2])
async def test_한_사이클을_돌면_리포트가_나온다(monkeypatch, hours_limit):
    google = _FakeGoogle()
    monkeypatch.setattr("app.adapters.google.get_places_client", lambda: google)
    monkeypatch.setattr(
        "app.adapters.localdata.get_localdata_registry", lambda: LocalDataRegistry()
    )
    report = await run(
        DISTRICTS[:1], hours_limit=hours_limit, ratings_limit=0, kakao=_FakeKakao()
    )
    assert report.collected == report.upserted > 0
    assert report.hours_filled == hours_limit
    assert report.districts == [DISTRICTS[0].name]
