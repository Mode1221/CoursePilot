"""종료 시각 표현("11시 전에는 끝내고")과 싫다고 말한 성격."""
from datetime import time

import pytest

from app.pipeline.decomposition import parse_constraints


@pytest.mark.parametrize(
    "text,expected",
    [
        ("내일 저녁 7시 반에 시작해서 11시 전에는 끝내고 싶어", time(23, 0)),
        ("10시 전에 마무리", time(22, 0)),
        ("9시 이전에 끝났으면 해", time(21, 0)),
        ("6시에 만나서 11시까지", time(23, 0)),
    ],
)
def test_끝내는_시각을_읽는다(text, expected):
    assert parse_constraints(text).end_time == expected


def test_끝만_말하면_시작은_비워둔다():
    c = parse_constraints("10시 전에 마무리")
    assert c.start_time is None and c.duration_min is None


def test_시작과_끝을_모두_말하면_소요시간까지_계산한다():
    c = parse_constraints("내일 저녁 7시 반에 시작해서 11시 전에는 끝내고 싶어")
    assert (c.start_time, c.end_time, c.duration_min) == (time(19, 30), time(23, 0), 210)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("웨이팅 긴 데는 싫어", "웨이팅"),
        ("시끄러운 곳은 별로", "시끄러운"),
        ("좁은 데는 피하고 싶어", "좁은"),
    ],
)
def test_싫다고_말한_성격은_제외_조건이다(text, expected):
    assert expected in parse_constraints(text).exclude_keywords


def test_기존_제외_표현은_그대로_동작한다():
    assert "매운" in parse_constraints("매운 건 빼고").exclude_keywords


def test_범위_표현은_영향을_받지_않는다():
    c = parse_constraints("7시부터 10시까지 홍대")
    assert (c.start_time, c.end_time) == (time(7, 0), time(10, 0))
