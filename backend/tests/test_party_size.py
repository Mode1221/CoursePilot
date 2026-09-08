from app.pipeline.decomposition import parse_constraints


def test_party_size_from_number():
    assert parse_constraints("3인 강남 2만원").party_size == 3
    assert parse_constraints("4명이서 성수동 저녁").party_size == 4


def test_party_size_from_word():
    assert parse_constraints("혼자 홍대 카페").party_size == 1
    assert parse_constraints("둘이 조용한 곳").party_size == 2


def test_total_budget_is_divided_per_person():
    c = parse_constraints("4명이서 총 20만원 성수동 저녁")
    assert c.party_size == 4
    assert c.budget_max == 50_000


def test_per_person_budget_kept():
    c = parse_constraints("3인 강남 2만원")
    assert c.budget_max == 20_000


def test_no_party_size_when_absent():
    assert parse_constraints("30분 걸어서 성수동").party_size is None
