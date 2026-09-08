from app.pipeline.decomposition import parse_constraints
from app.pipeline.planner import desired_slots


def test_stop_count_from_number():
    assert parse_constraints("성수동 저녁 7시 2차까지").stop_count == 2
    assert parse_constraints("홍대 3곳 돌래").stop_count == 3


def test_stop_count_from_word():
    assert parse_constraints("홍대 세 군데 돌래").stop_count == 3


def test_stop_count_overrides_duration_slots():
    c = parse_constraints("성수동 저녁 6시 5시간 2차까지")
    assert len(desired_slots(c)) == 2


def test_no_stop_count_when_absent():
    assert parse_constraints("강남 저녁 5시간").stop_count is None


def test_한_곳만_요청하면_한_칸이다():
    from datetime import time

    from app.pipeline.planner import desired_slots
    from app.schemas import PlanConstraints

    assert desired_slots(PlanConstraints(stop_count=1, start_time=time(19, 0))) == ["meal"]
    assert desired_slots(PlanConstraints(stop_count=1, start_time=time(15, 0))) == ["cafe"]
