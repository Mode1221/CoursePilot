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
