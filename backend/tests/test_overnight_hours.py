from datetime import time

from app.pipeline.validation import is_open_at, is_open_during
from app.schemas import Place


def _place(open_h: int, close_h: int, **kw) -> Place:
    return Place(
        id="p", name="p", lat=37.5, lng=127.0,
        open_time=time(open_h, 0), close_time=time(close_h, 0), **kw
    )


def test_새벽에_닫는_가게는_밤에_영업으로_본다():
    bar = _place(18, 2)  # 18:00 ~ 02:00
    assert is_open_at(bar, time(23, 0))
    assert is_open_at(bar, time(1, 0))
    assert not is_open_at(bar, time(15, 0))
    assert not is_open_at(bar, time(3, 0))


def test_새벽_마감_체류_구간_검증():
    bar = _place(18, 2)
    assert is_open_during(bar, time(23, 0), time(1, 0))  # 자정을 넘겨 머무름
    assert not is_open_during(bar, time(1, 0), time(3, 0))  # 마감 이후까지 머무름


def test_일반_영업시간은_기존과_동일():
    cafe = _place(9, 21)
    assert is_open_during(cafe, time(10, 0), time(12, 0))
    assert not is_open_during(cafe, time(20, 0), time(22, 0))
    assert not is_open_at(cafe, time(8, 0))


def test_브레이크타임은_새벽_영업에도_적용된다():
    bar = _place(18, 2, break_start=time(20, 0), break_end=time(21, 0))
    assert not is_open_at(bar, time(20, 30))
    assert is_open_at(bar, time(22, 0))
