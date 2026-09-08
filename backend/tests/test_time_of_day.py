from datetime import time

from app.pipeline.decomposition import parse_constraints


def test_저녁_밤은_오후로_해석한다():
    assert parse_constraints("저녁 7시 홍대").start_time == time(19, 0)
    assert parse_constraints("밤 9시 강남").start_time == time(21, 0)
    assert parse_constraints("낮 1시 성수동").start_time == time(13, 0)


def test_오전_아침_새벽은_그대로():
    assert parse_constraints("아침 8시").start_time == time(8, 0)
    assert parse_constraints("새벽 2시").start_time == time(2, 0)
    assert parse_constraints("오전 10시").start_time == time(10, 0)


def test_시각_없이_시간대만_말해도_기본값을_잡는다():
    assert parse_constraints("저녁에 연남 가자").start_time == time(18, 0)
    assert parse_constraints("점심에 성수동").start_time == time(12, 0)


def test_시간대_표현이_없으면_미지정():
    assert parse_constraints("성수동 카페 3시간").start_time is None


def test_분과_반도_함께_해석한다():
    assert parse_constraints("저녁 7시 30분").start_time == time(19, 30)
    assert parse_constraints("저녁 7시반").start_time == time(19, 30)
