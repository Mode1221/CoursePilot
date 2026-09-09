from app.pipeline.decomposition import parse_constraints


def test_range_with_tilde_uses_upper_bound():
    assert parse_constraints("성수동 3~5만원 저녁").budget_max == 50_000


def test_range_with_words_uses_upper_bound():
    assert parse_constraints("강남 3만원에서 5만원").budget_max == 50_000


def test_single_amount_unchanged():
    assert parse_constraints("홍대 2만원").budget_max == 20_000


def test_total_budget_division_still_works():
    c = parse_constraints("4명이서 총 20만원 성수동")
    assert c.budget_max == 50_000


def test_인당_표현은_인원수가_아니다():
    from app.pipeline.decomposition import parse_constraints

    c = parse_constraints("1인당 2만원")
    assert c.budget_max == 20000
    assert c.party_size is None  # "1인당"은 단가 표현

    # 진짜 인원 표현은 그대로
    assert parse_constraints("4명 저녁").party_size == 4


def test_원을_생략한_금액도_예산으로_본다():
    from app.pipeline.decomposition import parse_constraints

    assert parse_constraints("1인 3만").budget_max == 30000
    assert parse_constraints("10만 원").budget_max == 100000
