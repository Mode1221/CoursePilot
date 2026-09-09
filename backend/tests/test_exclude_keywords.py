from app.pipeline.decomposition import parse_constraints
from app.pipeline.planner import score_place
from app.schemas import Place, PlanConstraints


def test_exclusion_removes_from_keywords():
    c = parse_constraints("성수동 술집 빼고 저녁")
    assert c.exclude_keywords == ["술집"]
    assert "술집" not in c.keywords


def test_other_keywords_kept():
    c = parse_constraints("홍대 카페 말고 맛집")
    assert c.exclude_keywords == ["카페"]
    assert "맛집" in c.keywords


def test_no_exclusion_by_default():
    assert parse_constraints("조용한 성수동").exclude_keywords == []


def test_excluded_place_is_penalized():
    c = PlanConstraints(exclude_keywords=["술집"])
    bar = Place(id="b", name="성수 술집", category="bar", lat=37.5, lng=127.0)
    cafe = Place(id="c", name="성수 카페", category="cafe", lat=37.5, lng=127.0)
    assert score_place(bar, c, None) < score_place(cafe, c, None)


def test_제외어에_붙은_조사를_떼어낸다():
    c = parse_constraints("7시에 회식, 술은 빼고")
    assert c.exclude_keywords == ["술"]


def test_한_글자_제외어도_인식한다():
    assert parse_constraints("술 빼고 성수동").exclude_keywords == ["술"]


def test_제외어와_겹치는_키워드는_검색어에서_뺀다():
    c = parse_constraints("성수동에서 술집 빼고 카페 위주로")
    assert "술집" not in c.keywords
    assert "카페" in c.keywords


def test_장소_성격_표현을_검색어로_넘긴다():
    assert "한정식" in parse_constraints("부모님이랑 점심 한정식").keywords
    assert "노포" in parse_constraints("을지로 노포 투어").keywords
