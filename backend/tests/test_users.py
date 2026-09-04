import pytest

from app.pipeline.agent import _apply_preferences
from app.schemas import PlanConstraints, TravelMode
from app.users import CreditError, Preferences, UserStore


def test_credit_consume_and_exhaust():
    us = UserStore()
    user = us.create("010-0000-0000", credits_limit=2)
    us.consume_credit(user.id)
    us.consume_credit(user.id)
    with pytest.raises(CreditError):
        us.consume_credit(user.id)
    assert us.get(user.id).credits_left == 0


def test_preferences_autofill():
    us = UserStore()
    user = us.create("010-1111-1111")
    us.set_preferences(user.id, Preferences(region="성수동", mood="조용한", transport="차량"))
    prefs = us.get(user.id).preferences.model_dump()

    c = PlanConstraints()  # 아무 조건 없음
    _apply_preferences(c, prefs)
    assert c.region == "성수동"
    assert "조용한" in c.keywords
    assert c.travel_mode == TravelMode.CAR


def test_preferences_do_not_override_explicit():
    c = PlanConstraints(region="강남역")
    _apply_preferences(c, {"region": "성수동"})
    assert c.region == "강남역"  # 명시값 유지
