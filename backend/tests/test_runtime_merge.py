"""런타임에서 저장된 보강 값을 검색 결과에 얹는다.

카카오·네이버 응답에는 영업시간도 평점도 없다. 병합하지 않으면 코스를 확정할
때마다 확정 장소 전부가 stale 로 보여 Google Enterprise 콜(월 1,000)을 태운다.
"""
from datetime import UTC, datetime, time

import pytest

from app.adapters.google import hours_stale, refresh_final_hours
from app.adapters.map_service import MapService, StoredMergeMapService
from app.places import place_repo
from app.schemas import Place


def _place(pid="kakao-1", **kw) -> Place:
    base = {
        "id": pid, "name": "성수커피", "address": "서울 성동구 아차산로 17",
        "lat": 37.54, "lng": 127.05,
    }
    return Place(**{**base, **kw})


def _stored(pid="kakao-1", **kw) -> Place:
    return _place(
        pid,
        open_time=time(11, 0),
        close_time=time(22, 0),
        hours_checked_at=datetime.now(UTC),
        rating=4.4,
        rating_count=210,
        rating_checked_at=datetime.now(UTC),
        google_place_id="gp-1",
        **kw,
    )


class _Vendor(MapService):
    """카카오·네이버처럼 영업시간·평점이 없는 응답."""

    def __init__(self, places):
        self._places = places

    async def search_places(self, region, keywords, limit=10):
        return [p.model_copy(deep=True) for p in self._places]

    async def get_route(self, origin, dest, mode):
        raise NotImplementedError


@pytest.fixture(autouse=True)
def _clean_repo():
    place_repo._mem.clear()
    yield
    place_repo._mem.clear()


async def test_같은_id면_저장된_영업시간과_평점을_얹는다():
    place_repo.upsert_many([_stored()])
    svc = StoredMergeMapService(_Vendor([_place()]))
    (merged,) = await svc.search_places("성수", ["카페"])
    assert merged.open_time == time(11, 0)
    assert (merged.rating, merged.rating_count) == (4.4, 210)
    assert merged.google_place_id == "gp-1"
    assert merged.hours_checked_at is not None


async def test_id가_달라도_상호와_주소로_맞춘다():
    """네이버 결과는 카카오 id 와 다르다 — 그때도 보강 값을 살려야 한다."""
    place_repo.upsert_many([_stored("kakao-1")])
    svc = StoredMergeMapService(_Vendor([_place("naver-99", name="성수 커피")]))
    (merged,) = await svc.search_places("성수", ["카페"])
    assert merged.rating == 4.4 and merged.google_place_id == "gp-1"


async def test_저장된_것이_없으면_그대로_통과한다():
    svc = StoredMergeMapService(_Vendor([_place()]))
    (merged,) = await svc.search_places("성수", ["카페"])
    assert merged.rating is None and merged.hours_checked_at is None


async def test_병합된_장소는_구글에_다시_묻지_않는다(monkeypatch):
    """이 PR 의 핵심 — 병합 전에는 코스 확정 장소 전부를 Google 에 물었다."""
    place_repo.upsert_many([_stored()])
    svc = StoredMergeMapService(_Vendor([_place()]))
    (merged,) = await svc.search_places("성수", ["카페"])
    assert not hours_stale(merged)

    calls: list[str] = []

    class _Client:
        enabled = True

        async def refresh_details(self, place, weekday=None):
            calls.append(place.id)
            return place

    monkeypatch.setattr("app.adapters.google.get_places_client", lambda: _Client())
    await refresh_final_hours([merged])
    assert calls == []  # Google 콜 0회


async def test_병합되지_않은_장소는_여전히_갱신_대상(monkeypatch):
    svc = StoredMergeMapService(_Vendor([_place("kakao-2", name="새로운집")]))
    (fresh,) = await svc.search_places("성수", ["카페"])
    assert hours_stale(fresh)


async def test_병합된_평점이_스코어링에_반영된다():
    """병합이 없으면 rating 이 None 이라 평점 가중치가 통째로 빠진다."""
    from app.pipeline.planner import PlanConstraints, score_place

    place_repo.upsert_many([_stored()])
    svc = StoredMergeMapService(_Vendor([_place()]))
    (merged,) = await svc.search_places("성수", ["카페"])
    constraints = PlanConstraints()
    assert score_place(merged, constraints, None) > score_place(_place(), constraints, None)
