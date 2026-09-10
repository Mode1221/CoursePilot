"""소요 시간 파싱 경계."""
from app.pipeline.decomposition import parse_constraints


def test_긴_숫자를_시간으로_잘라_읽지_않는다():
    """'1000시간' 에서 뒤 두 자리를 '00시간' 으로 읽어 0분짜리 코스가 됐었다."""
    assert parse_constraints("성수동 1000시간 코스").duration_min is None
    assert parse_constraints("성수동 100시간").duration_min is None


def test_비현실적인_소요_시간은_하루_범위로_조정한다():
    from app.pipeline.decomposition import MAX_DURATION_MIN, MIN_DURATION_MIN

    assert parse_constraints("성수동 20시간").duration_min == MAX_DURATION_MIN
    assert parse_constraints("성수동 0시간").duration_min == MIN_DURATION_MIN


def test_시작보다_이른_종료는_다음날이_아니라_상한으로_본다():
    from app.pipeline.decomposition import MAX_DURATION_MIN

    c = parse_constraints("성수동 오전 10시부터 오전 9시까지")
    assert c.duration_min == MAX_DURATION_MIN
    # 종료 시각도 조정된 소요 시간에 맞춘다(둘이 어긋나면 타임라인이 깨진다)
    assert c.end_time.hour == (10 + MAX_DURATION_MIN // 60) % 24
