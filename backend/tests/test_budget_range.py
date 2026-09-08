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
