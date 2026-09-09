"""갱신 정책: 폐업은 전체·주 1회, 유료 콜은 활성 집합(최근 90일)만."""
from datetime import UTC, datetime, timedelta

from app.adapters.google import GooglePlacesClient
from app.adapters.localdata import LocalDataRegistry
from app.batch.refresh import (
    ACTIVE_WINDOW_DAYS,
    is_active,
    refresh_closures,
    refresh_on_demand,
    run,
)
from app.places import place_repo
from app.schemas import Place

CSV = """사업장명,도로명전체주소,상세영업상태명,인허가일자,폐업일자
살아있는집,서울 성동구 아차산로 17,영업/정상,20150301,
문닫은집,서울 성동구 아차산로 21,폐업,20180401,20220501
"""


def _place(pid, name="가게", address=None, days_ago=None) -> Place:
    seen = None if days_ago is None else datetime.now(UTC) - timedelta(days=days_ago)
    return Place(
        id=pid, name=name, address=address, lat=37.5, lng=127.0, last_recommended_at=seen
    )


def test_최근_추천된_장소만_활성이다():
    assert is_active(_place("a", days_ago=1))
    assert is_active(_place("a", days_ago=ACTIVE_WINDOW_DAYS - 1))
    assert not is_active(_place("a", days_ago=ACTIVE_WINDOW_DAYS + 1))
    assert not is_active(_place("a"))


def test_naive_시각도_활성_판정에_쓰인다():
    place = _place("a")
    place.last_recommended_at = datetime.now(UTC).replace(tzinfo=None)
    assert is_active(place)


def _registry(monkeypatch, csv=CSV):
    registry = LocalDataRegistry()
    if csv:
        registry.load_csv(csv)
    monkeypatch.setattr("app.adapters.localdata.get_localdata_registry", lambda: registry)
    return registry


def test_폐업은_저장된_전체에서_제거한다(monkeypatch):
    _registry(monkeypatch)
    places = [
        _place("a", "살아있는집", "서울 성동구 아차산로 17"),
        _place("b", "문닫은집", "서울 성동구 아차산로 21"),
    ]
    kept, removed, filled = refresh_closures(places)
    assert [p.id for p in kept] == ["a"] and removed == 1 and filled == 1


def test_대장이_없으면_아무것도_지우지_않는다(monkeypatch):
    _registry(monkeypatch, csv="")
    kept, removed, filled = refresh_closures([_place("b", "문닫은집")])
    assert len(kept) == 1 and removed == 0 and filled == 0


class _FakeGoogle(GooglePlacesClient):
    def __init__(self, enabled=True):
        self._key = "k" if enabled else ""
        self.hours: list[str] = []

    async def refresh_hours(self, place, weekday=None):
        self.hours.append(place.id)
        place.hours_checked_at = datetime.now(UTC)
        return place

    async def refresh_rating(self, place):
        place.rating_checked_at = datetime.now(UTC)
        return place


async def test_비활성_장소에는_유료_콜을_쓰지_않는다(monkeypatch):
    google = _FakeGoogle()
    monkeypatch.setattr("app.adapters.google.get_places_client", lambda: google)
    _registry(monkeypatch, csv="")
    place_repo._mem.clear()
    place_repo.upsert_many([_place("active", days_ago=3), _place("stale", days_ago=200)])
    report = await run(ratings_limit=0)
    assert google.hours == ["active"]
    assert report.active == 1 and report.scanned == 2
    place_repo._mem.clear()


async def test_폐업은_저장소에서도_지워진다(monkeypatch):
    monkeypatch.setattr("app.adapters.google.get_places_client", lambda: _FakeGoogle(False))
    _registry(monkeypatch)
    place_repo._mem.clear()
    place_repo.upsert_many(
        [
            _place("a", "살아있는집", "서울 성동구 아차산로 17", days_ago=1),
            _place("b", "문닫은집", "서울 성동구 아차산로 21", days_ago=1),
        ]
    )
    report = await run()
    assert report.closed_removed == 1
    assert set(place_repo.get_many(["a", "b"])) == {"a"}
    place_repo._mem.clear()


async def test_활성_집합_밖은_재등장_시_즉석_갱신한다(monkeypatch):
    google = _FakeGoogle()
    monkeypatch.setattr("app.adapters.google.get_places_client", lambda: google)
    old = _place("old", days_ago=200)
    fresh = _place("fresh")
    fresh.hours_checked_at = datetime.now(UTC)
    await refresh_on_demand([old, fresh])
    assert google.hours == ["old"]


async def test_키가_없으면_즉석_갱신도_건너뛴다(monkeypatch):
    monkeypatch.setattr("app.adapters.google.get_places_client", lambda: _FakeGoogle(False))
    place = _place("old", days_ago=200)
    await refresh_on_demand([place])
    assert place.hours_checked_at is None
