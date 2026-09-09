"""기념일 표현("크리스마스에")도 날짜로 읽는다."""
from datetime import date

import pytest

from app.pipeline.decomposition import HOLIDAYS, _parse_date, parse_constraints

TODAY = date(2026, 9, 9)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("크리스마스에 데이트", date(2026, 12, 25)),
        ("크리스마스이브에 저녁", date(2026, 12, 24)),
        ("성탄절 코스", date(2026, 12, 25)),
        ("한글날 나들이", date(2026, 10, 9)),
    ],
)
def test_기념일을_날짜로_읽는다(text, expected):
    assert _parse_date(text, TODAY) == expected


def test_이미_지난_기념일은_내년으로_본다():
    assert _parse_date("발렌타인데이 코스", TODAY) == date(2027, 2, 14)
    assert _parse_date("어린이날", TODAY) == date(2027, 5, 5)


def test_긴_이름을_먼저_본다():
    # "크리스마스이브"가 "크리스마스"로 잘리면 하루 어긋난다
    assert _parse_date("크리스마스이브", TODAY) == date(2026, 12, 24)


def test_숫자_날짜가_있으면_그대로_쓴다():
    assert parse_constraints("12월 24일 저녁 7시").plan_date == date(2026, 12, 24)


def test_기념일이_없으면_None():
    assert _parse_date("성수동 카페", TODAY) is None


def test_사전은_월일_쌍이다():
    assert all(1 <= m <= 12 and 1 <= d <= 31 for m, d in HOLIDAYS.values())
