from datetime import date

from app.pipeline.decomposition import parse_constraints

TUESDAY = date(2026, 9, 8)


def test_relative_day():
    assert parse_constraints("내일 저녁 7시 성수동", today=TUESDAY).plan_date == date(2026, 9, 9)
    assert parse_constraints("모레 홍대", today=TUESDAY).plan_date == date(2026, 9, 10)


def test_this_week_weekday():
    assert parse_constraints("이번 주 토요일 홍대", today=TUESDAY).plan_date == date(2026, 9, 12)


def test_next_week_weekday():
    assert parse_constraints("다음 주 금요일 강남", today=TUESDAY).plan_date == date(2026, 9, 18)


def test_month_day():
    assert parse_constraints("12월 3일 저녁 성수동", today=TUESDAY).plan_date == date(2026, 12, 3)


def test_past_month_day_rolls_to_next_year():
    assert parse_constraints("1월 5일 강남", today=TUESDAY).plan_date == date(2027, 1, 5)


def test_no_date_when_absent():
    assert parse_constraints("성수동 저녁 7시", today=TUESDAY).plan_date is None
