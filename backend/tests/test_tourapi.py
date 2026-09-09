"""TourAPI 보강: 등재 표시 + 관광·문화시설 이용시간."""
from datetime import time

import pytest

from app.adapters.naver import _directions_headers
from app.adapters.tourapi import TourApiClient, parse_hours
from app.config import settings
from app.schemas import Place


def _place() -> Place:
    return Place(id="p", name="서울숲", lat=37.5, lng=127.0, hours_unverified=True)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("09:00 ~ 18:00", ("09:00", "18:00")),
        ("10:30~19:00 (입장마감 18:30)", ("10:30", "19:00")),
        ("상시개방", None),
        (None, None),
        ("99:00 ~ 18:00", None),
        ("00:00 ~ 24:00", ("00:00", "00:00")),
    ],
)
def test_자유서술_이용시간을_파싱한다(text, expected):
    assert parse_hours(text) == expected


class _Fake(TourApiClient):
    def __init__(self, item, intro):
        self._key = "k"
        self._item = item
        self._intro = intro

    async def find(self, name):
        return self._item

    async def intro(self, content_id, content_type_id):
        return self._intro


async def test_문화시설_이용시간을_채우고_등재를_표시한다():
    client = _Fake({"contentid": "1", "contenttypeid": "14"}, {"usetimeculture": "10:00 ~ 19:00"})
    place = await client.enrich(_place())
    assert place.tour_listed is True
    assert (place.open_time, place.close_time) == (time(10, 0), time(19, 0))
    assert place.hours_unverified is False


async def test_관광지는_usetime_필드를_본다():
    client = _Fake({"contentid": "1", "contenttypeid": "12"}, {"usetime": "05:00 ~ 23:00"})
    place = await client.enrich(_place())
    assert place.open_time == time(5, 0)


async def test_등재만_되고_시간이_없으면_확인_필요로_남는다():
    client = _Fake({"contentid": "1", "contenttypeid": "14"}, {"usetimeculture": "상시개방"})
    place = await client.enrich(_place())
    assert place.tour_listed is True and place.hours_unverified is True


async def test_등재되지_않은_장소는_그대로다():
    place = await _Fake(None, None).enrich(_place())
    assert place.tour_listed is False and place.open_time is None


async def test_호출_실패는_무영향():
    class _Broken(_Fake):
        async def find(self, name):
            raise RuntimeError("boom")

    place = await _Broken(None, None).enrich(_place())
    assert place.open_time is None


async def test_키가_없으면_아무것도_하지_않는다():
    client = TourApiClient()
    client._key = ""
    assert not client.enabled
    assert await client.find("서울숲") is None
    assert await client.intro("1", "12") is None


def test_경로_키는_NCP_전용키를_우선한다(monkeypatch):
    monkeypatch.setattr(settings, "ncp_api_key_id", "ncp-id")
    monkeypatch.setattr(settings, "ncp_api_key", "ncp-secret")
    headers = _directions_headers()
    assert headers["X-NCP-APIGW-API-KEY-ID"] == "ncp-id"
    assert headers["X-NCP-APIGW-API-KEY"] == "ncp-secret"


def test_NCP_키가_없으면_개발자센터_키로_폴백(monkeypatch):
    monkeypatch.setattr(settings, "ncp_api_key_id", "")
    monkeypatch.setattr(settings, "ncp_api_key", "")
    monkeypatch.setattr(settings, "naver_client_id", "dev-id")
    monkeypatch.setattr(settings, "naver_client_secret", "dev-secret")
    assert _directions_headers()["X-NCP-APIGW-API-KEY-ID"] == "dev-id"
