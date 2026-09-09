"""Google Places 티어 분리: 영업시간/평점 콜을 섞지 않고 TTL 안에서 재사용한다."""
from datetime import UTC, datetime, time, timedelta

import pytest

from app.adapters.google import (
    HOURS_MASK,
    IDS_ONLY_MASK,
    MIN_RATING_COUNT,
    RATING_MASK,
    GooglePlacesClient,
    get_places_client,
    hours_stale,
    is_permanently_closed,
    rating_stale,
    refresh_final_hours,
)
from app.schemas import Place

HOURS_PAYLOAD = {
    "businessStatus": "OPERATIONAL",
    "regularOpeningHours": {
        "periods": [
            # Google: 일=0. 아래는 월요일 11:00~22:00.
            {"open": {"day": 1, "hour": 11, "minute": 0}, "close": {"day": 1, "hour": 22, "minute": 0}}
        ]
    },
}


def _place(**kw) -> Place:
    base = {"id": "p1", "name": "성수커피", "lat": 37.5, "lng": 127.0}
    return Place(**{**base, **kw})


class _FakeClient(GooglePlacesClient):
    def __init__(self, hours=HOURS_PAYLOAD, rating=(4.3, 120)):
        self._key = "test-key"
        self._hours = hours
        self._rating = rating
        self.calls: list[str] = []

    async def map_place_id(self, place):
        self.calls.append("map")
        return "gp-1"

    async def fetch_hours(self, place_id):
        self.calls.append("hours")
        return self._hours

    async def fetch_rating(self, place_id):
        self.calls.append("rating")
        return self._rating


def test_필드마스크가_티어별로_분리돼_있다():
    assert IDS_ONLY_MASK == "places.id"
    assert "rating" not in HOURS_MASK and "userRatingCount" not in HOURS_MASK
    assert "OpeningHours" not in RATING_MASK and "businessStatus" not in RATING_MASK


def test_TTL이_지나야_stale():
    now = datetime.now(UTC)
    assert hours_stale(_place())
    assert not hours_stale(_place(hours_checked_at=now - timedelta(days=29)))
    assert hours_stale(_place(hours_checked_at=now - timedelta(days=31)))
    assert not rating_stale(_place(rating_checked_at=now - timedelta(days=89)))
    assert rating_stale(_place(rating_checked_at=now - timedelta(days=91)))


async def test_영업시간_갱신은_매핑_1콜_상세_1콜():
    client = _FakeClient()
    place = await client.refresh_hours(_place(), weekday=0)
    assert client.calls == ["map", "hours"]
    assert (place.open_time, place.close_time) == (time(11, 0), time(22, 0))
    assert place.business_status == "OPERATIONAL"
    assert place.hours_checked_at is not None
    assert not place.hours_unverified


async def test_place_id를_알면_매핑을_건너뛴다():
    client = _FakeClient()
    await client.refresh_hours(_place(google_place_id="gp-1"), weekday=0)
    assert client.calls == ["hours"]


async def test_TTL_안이면_호출하지_않는다():
    client = _FakeClient()
    fresh = _place(hours_checked_at=datetime.now(UTC) - timedelta(days=1))
    await client.refresh_hours(fresh)
    assert client.calls == []


async def test_영업시간이_없으면_확인_필요로_표시한다():
    client = _FakeClient(hours={"businessStatus": "OPERATIONAL"})
    place = await client.refresh_hours(_place(), weekday=0)
    assert place.hours_unverified is True


async def test_호출_실패는_코스를_깨지_않고_확인_필요로_남는다():
    class _Broken(_FakeClient):
        async def fetch_hours(self, place_id):
            raise RuntimeError("boom")

    place = await _Broken().refresh_hours(_place(), weekday=0)
    assert place.hours_unverified is True
    assert place.open_time is None


async def test_평가수가_적으면_평점을_쓰지_않는다():
    client = _FakeClient(rating=None)
    place = await client.refresh_rating(_place())
    assert place.rating is None
    assert place.rating_checked_at is not None  # 다시 묻지 않도록 시각은 남긴다
    assert MIN_RATING_COUNT == 30


async def test_평점_갱신은_평점_콜만_쓴다():
    client = _FakeClient()
    place = await client.refresh_rating(_place(google_place_id="gp-1"))
    assert client.calls == ["rating"]
    assert (place.rating, place.rating_count) == (4.3, 120)


async def test_확정_코스만_갱신한다(monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr("app.adapters.google.get_places_client", lambda: client)
    fresh = _place(id="p2", hours_checked_at=datetime.now(UTC))
    await refresh_final_hours([_place(), fresh])
    assert client.calls.count("hours") == 1


async def test_키가_없으면_아무것도_하지_않는다(monkeypatch):
    client = GooglePlacesClient()
    client._key = ""
    assert await client.map_place_id(_place()) is None
    assert await client.fetch_hours("gp-1") is None
    place = await client.refresh_hours(_place())
    assert place.hours_checked_at is None


def test_영구폐업을_식별한다():
    assert is_permanently_closed(_place(business_status="CLOSED_PERMANENTLY"))
    assert not is_permanently_closed(_place(business_status="OPERATIONAL"))


def test_client_는_싱글턴이다():
    assert get_places_client() is get_places_client()


@pytest.mark.parametrize("weekday,expected", [(0, time(11, 0)), (2, None)])
async def test_요일별_영업시간을_고른다(weekday, expected):
    place = await _FakeClient().refresh_hours(_place(), weekday=weekday)
    assert place.open_time == expected
