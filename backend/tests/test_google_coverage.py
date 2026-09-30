"""영업시간·평점 채우기: 상권 × 칸별 상위 후보, 설정으로 월 상한·하루 양·주기."""
from datetime import UTC, datetime, timedelta

from app.batch.places_build import core_targets
from app.config import settings
from app.schemas import Place


def _p(pid, lat, lng, cat, blog=0):
    return Place(id=pid, name=pid, category=cat, lat=lat, lng=lng, blog_mentions=blog)


def test_상권_칸마다_상위만_번갈아_고른다(monkeypatch):
    seongsu = (37.5445, 127.0557)
    yeonnam = (37.5610, 126.9250)
    places = [
        *[_p(f"s-meal-{i}", *seongsu, "음식점 > 한식", blog=i) for i in range(5)],
        *[_p(f"s-cafe-{i}", *seongsu, "카페", blog=i) for i in range(5)],
        *[_p(f"y-meal-{i}", *yeonnam, "음식점 > 양식", blog=i) for i in range(5)],
    ]
    out = core_targets(places, per_slot=2)
    assert len(out) == 6  # 3묶음 × 2
    assert {p.id for p in out[:3]} == {"s-meal-4", "s-cafe-4", "y-meal-4"}  # 묶음마다 1등부터 번갈아


def test_월_상한과_주기는_설정을_따른다(monkeypatch):
    from app.adapters.google import hours_stale
    from app.quota import quota_store

    monkeypatch.setattr(settings, "google_details_monthly", 3500)
    assert quota_store.limit("google.details") == 3500
    monkeypatch.setattr(settings, "google_hours_ttl_days", 60)
    place = Place(id="x", name="x", lat=37.5, lng=127.0, hours_checked_at=datetime.now(UTC) - timedelta(days=45))
    assert hours_stale(place) is False


def test_하루_배치량을_올리면_하루_상한도_오른다(monkeypatch):
    from app import usage

    monkeypatch.setattr(settings, "google_details_per_day", 300)
    assert usage._global_limit("google.details") == 300 + usage.RUNTIME_DETAILS_PER_DAY


def test_배치를_늘리면_place_id_찾기_상한도_늘어난다(monkeypatch):
    from app import usage
    from app.quota import quota_store

    monkeypatch.setattr(settings, "google_details_per_day", 300)
    assert usage._global_limit("google.map_id") == usage.GLOBAL_DAILY["google.map_id"] + 300
    assert quota_store.limit("google.map_id") >= 10_000 + 280 * 30


def test_월_카운터는_Google_청구_월_태평양_시간_기준():
    from app.quota import _month_key

    # 한국 10월 1일 10시 = UTC 10월 1일 01시 = 태평양 9월 30일 18시 → 아직 9월
    assert _month_key(datetime(2026, 10, 1, 1, 0, tzinfo=UTC)) == "2026-09"
    assert _month_key(datetime(2026, 10, 1, 8, 0, tzinfo=UTC)) == "2026-10"
