"""우천 대체 코스: 실내 위주 선호."""
from app.pipeline.decomposition import parse_constraints
from app.pipeline.planner import score_place
from app.schemas import Place, PlanConstraints


def _place(name: str, category: str) -> Place:
    return Place(id=name, name=name, category=category, lat=37.5, lng=127.0)


def test_비_표현을_인식한다():
    c = parse_constraints("내일 비 온대 홍대에서 놀자")
    assert c.prefer_indoor is True
    assert c.keywords[0] == "실내"


def test_비_얘기가_없으면_꺼둔다():
    assert parse_constraints("성수동 카페 추천").prefer_indoor is False


def test_우천이면_야외보다_실내가_높다():
    c = PlanConstraints(prefer_indoor=True)
    indoor = _place("성수 전시관", "gallery")
    outdoor = _place("한강 공원 산책", "park")
    assert score_place(indoor, c, None) > score_place(outdoor, c, None)


def test_평상시엔_야외를_깎지_않는다():
    c = PlanConstraints()
    outdoor = _place("한강 공원 산책", "park")
    assert score_place(outdoor, c, None) == score_place(outdoor, PlanConstraints(), None)
