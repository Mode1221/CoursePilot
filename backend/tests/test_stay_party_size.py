from app.pipeline.validation import LARGE_PARTY_EXTRA_MIN, stay_minutes
from app.schemas import Place

RESTAURANT = Place(id="r", name="식당", category="restaurant", lat=37.5, lng=127.0)
CAFE = Place(id="c", name="카페", category="cafe", lat=37.5, lng=127.0)


def test_default_stay_unchanged():
    assert stay_minutes(RESTAURANT) == 90
    assert stay_minutes(CAFE) == 60


def test_small_party_unchanged():
    assert stay_minutes(RESTAURANT, 3) == 90


def test_large_party_gets_extra_time():
    assert stay_minutes(RESTAURANT, 6) == 90 + LARGE_PARTY_EXTRA_MIN
    assert stay_minutes(CAFE, 8) == 60 + LARGE_PARTY_EXTRA_MIN
