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


def _place(open_h=None, close_h=None):
    from app.schemas import Place

    return Place(
        id="p",
        name="가게",
        lat=37.5,
        lng=127.0,
        open_time=time(open_h, 0) if open_h is not None else None,
        close_time=time(close_h, 0) if close_h is not None else None,
    )


def _score(place, text):
    from app.pipeline.planner import score_place

    return score_place(place, parse_constraints(text), None)


def test_심야_요청이면_늦게까지_여는_곳이_높다():
    late = _place(18, 2)  # 자정 넘겨 새벽 2시까지
    early = _place(11, 21)
    assert _score(late, "새벽까지 하는 술집") > _score(early, "새벽까지 하는 술집")


def test_심야_요청이_아니면_가점하지_않는다():
    late, early = _place(18, 2), _place(11, 21)
    assert _score(late, "성수동 저녁") == _score(early, "성수동 저녁")


def test_영업시간을_모르면_가점하지_않는다():
    assert _score(_place(), "새벽까지 하는 술집") == _score(_place(11, 21), "새벽까지 하는 술집")
