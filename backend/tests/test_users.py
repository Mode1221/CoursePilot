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


def test_points_used_after_free_exhausted():
    us = UserStore()
    user = us.create("010-3", credits_limit=1)
    us.purchase_points(user.id, 2)
    assert us.get(user.id).credits_left == 3  # 무료1 + 포인트2
    us.consume_credit(user.id)  # 무료 소비
    us.consume_credit(user.id)  # 포인트 소비
    u = us.get(user.id)
    assert u.free_left == 0 and u.points == 1
    assert u.credits_left == 1


def test_points_carry_over_monthly_reset():
    us = UserStore()
    user = us.create("010-4", credits_limit=5)
    us.purchase_points(user.id, 3)
    # 지난 달로 위조 후 무료만 리셋되는지
    u = us.get(user.id)
    u.credit_period = "2000-01"
    u.credits_used = 5
    us._save(u)
    us.consume_credit(user.id)  # 리셋 → 무료 사용
    after = us.get(user.id)
    assert after.points == 3  # 포인트는 이월(리셋 영향 없음)


def test_refund_restores_used_not_limit():
    us = UserStore()
    user = us.create("010-2222-2222", credits_limit=5)
    us.consume_credit(user.id)
    us.refund_credit(user.id)
    u = us.get(user.id)
    assert u.credits_used == 0
    assert u.credits_limit == 5  # 한도는 그대로(영구 증가 아님)


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


def test_환불은_무료분을_먼저_복원한다():
    from app.users import UserStore

    store = UserStore()
    user = store.create("01000000000")
    store.consume_credit(user.id)
    refunded = store.refund_credit(user.id)
    assert refunded.credits_used == 0
    assert refunded.points == 0


def test_사용분이_없으면_포인트로_환불한다():
    from app.users import UserStore

    store = UserStore()
    user = store.create("01000000001")
    refunded = store.refund_credit(user.id)
    assert refunded.points == 1


def test_같은_번호로_다시_가입하면_기존_계정이다():
    from app.users import UserStore

    store = UserStore()
    first = store.create("01055556666")
    assert store.find_by_phone("01055556666").id == first.id
    assert store.find_by_phone("01000000999") is None
