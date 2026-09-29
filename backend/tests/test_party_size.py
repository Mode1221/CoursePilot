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


async def test_대인원이면_단체석을_검색어에_넣는다():
    from app.adapters.map_service import MockMapService
    from app.pipeline.agent import generate_course

    big = await generate_course("강남 6명 저녁", MockMapService())
    assert "단체석" in big.constraints.keywords

    small = await generate_course("강남 2명 저녁", MockMapService())
    assert "단체석" not in small.constraints.keywords


async def test_이미_말했으면_중복으로_넣지_않는다():
    from app.adapters.map_service import MockMapService
    from app.pipeline.agent import generate_course

    r = await generate_course("강남 8명 회식 룸 있는 곳", MockMapService())
    assert r.constraints.keywords == ["룸"]
