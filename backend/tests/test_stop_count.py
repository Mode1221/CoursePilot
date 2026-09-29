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


def test_한_곳_요청은_키워드_성격을_따른다():
    from app.pipeline.planner import desired_slots

    assert desired_slots(parse_constraints("강남 카페 한 곳 저녁 7시")) == ["cafe"]
    assert desired_slots(parse_constraints("성수동 술집 한 곳")) == ["bar"]
    assert desired_slots(parse_constraints("성수동 전시 한 곳")) == ["activity"]
    # 키워드가 없으면 기존대로 시간대 기준
    assert desired_slots(parse_constraints("강남 한 곳만 저녁 7시")) == ["meal"]


def test_다섯_여섯_곳도_인식하고_칸을_그만큼_만든다():
    assert parse_constraints("성수동 다섯 곳").stop_count == 5
    assert parse_constraints("성수동 여섯 군데").stop_count == 6
    assert len(desired_slots(parse_constraints("성수동 5곳 하루종일"))) == 5
    assert len(desired_slots(parse_constraints("성수동 6군데"))) == 6
    # 상한을 넘겨도 6칸까지만
    assert len(desired_slots(parse_constraints("성수동 9곳"))) == 6


def test_동행유형별_다섯칸_템플릿():
    assert desired_slots(parse_constraints("회식 5곳"))[-1] == "bar"
    assert "bar" not in desired_slots(parse_constraints("가족이랑 5곳"))
