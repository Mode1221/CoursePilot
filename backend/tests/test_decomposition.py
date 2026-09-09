

def test_자정을_넘겨도_종료_시각을_잡는다():
    from datetime import time

    from app.pipeline.decomposition import parse_constraints

    c = parse_constraints("밤 11시부터 3시간 성수동")
    assert c.start_time == time(23, 0)
    assert c.end_time == time(2, 0)
    assert c.duration_min == 180


def test_마커_없는_이른_시각은_저녁으로_본다():
    from datetime import time

    from app.pipeline.decomposition import parse_constraints

    assert parse_constraints("금요일 7시 강남역 회식").start_time == time(19, 0)
    assert parse_constraints("6시에 만나자").start_time == time(18, 0)
    # 오전을 뜻하는 표현이 있으면 그대로 둔다
    assert parse_constraints("아침 7시 조깅").start_time == time(7, 0)
    assert parse_constraints("7시 브런치").start_time == time(7, 0)
    assert parse_constraints("오전 7시 모임").start_time == time(7, 0)
    # 8시 이상은 그대로(오전 가능성이 높다)
    assert parse_constraints("8시 시작").start_time == time(8, 0)
