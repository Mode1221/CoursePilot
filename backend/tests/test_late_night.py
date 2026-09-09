"""심야 표현과 "없는" 제외."""
from datetime import time

import pytest

from app.pipeline.decomposition import parse_constraints


def test_새벽까지는_시작_시각이_아니다():
    c = parse_constraints("새벽까지 하는 술집")
    assert c.start_time is None
    assert "심야" in c.keywords


def test_새벽_시각_표현은_그대로_읽는다():
    assert parse_constraints("새벽 3시에 시작").start_time == time(3, 0)


@pytest.mark.parametrize("text", ["늦게까지 하는 곳", "밤늦게까지 여는 데", "늦은 시간까지"])
def test_늦게까지_여는_곳을_찾는다(text):
    assert "심야" in parse_constraints(text).keywords


@pytest.mark.parametrize(
    "text,excluded",
    [
        ("웨이팅 없는 데로", "웨이팅"),
        ("주차 걱정 없는 곳", "걱정"),
    ],
)
def test_없는_표현도_제외로_읽는다(text, excluded):
    assert excluded in parse_constraints(text).exclude_keywords


def test_시간대_표현은_그대로_동작한다():
    assert parse_constraints("저녁에 홍대").start_time == time(18, 0)
