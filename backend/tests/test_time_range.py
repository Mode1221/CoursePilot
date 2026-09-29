from datetime import time

from app.pipeline.decomposition import parse_constraints


def test_범위_표현은_종료_시각까지_잡는다():
    c = parse_constraints("저녁 7시부터 10시까지 홍대")
    assert (c.start_time, c.end_time, c.duration_min) == (time(19, 0), time(22, 0), 180)


def test_물결_표기도_인식한다():
    c = parse_constraints("오후 1시~5시 성수동")
    assert (c.start_time, c.end_time) == (time(13, 0), time(17, 0))


def test_앞뒤_시간대_표시가_다르면_각각_적용():
    c = parse_constraints("아침 10시부터 오후 3시까지")
    assert (c.start_time, c.end_time, c.duration_min) == (time(10, 0), time(15, 0), 300)


def test_자정을_넘는_범위는_다음날로_계산():
    c = parse_constraints("밤 10시부터 1시까지")
    assert c.duration_min == 180


def test_관용구도_소요시간으로_해석():
    assert parse_constraints("반나절 성수동").duration_min == 240
    assert parse_constraints("하루 종일 홍대").duration_min == 480


def test_기존_소요시간_표현은_그대로():
    c = parse_constraints("오전 10시 3시간 코스")
    assert (c.start_time, c.duration_min, c.end_time) == (time(10, 0), 180, time(13, 0))
