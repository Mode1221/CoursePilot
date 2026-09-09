"""요청한 사실 태그가 있는 곳이 평점 높은 곳보다 앞선다."""
from app.pipeline.planner import score_place
from app.schemas import Place, PlanConstraints


def _place(pid, rating, tags=(), cautions=()):
    return Place(
        id=pid,
        name=pid,
        category="restaurant",
        lat=37.5,
        lng=127.0,
        rating=rating,
        rating_count=200,
        fact_tags=list(tags),
        caution_tags=list(cautions),
    )


def test_요청한_태그가_평점을_이긴다():
    c = PlanConstraints(keywords=["단체석"])
    tagged = _place("tagged", 4.0, tags=["단체석"])
    higher_rating = _place("plain", 4.8)
    assert score_place(tagged, c, None) > score_place(higher_rating, c, None)


def test_불가로_확인된_곳은_더_낮다():
    c = PlanConstraints(keywords=["단체석"])
    blocked = _place("blocked", 4.8, cautions=["단체석"])
    plain = _place("plain", 4.0)
    assert score_place(blocked, c, None) < score_place(plain, c, None)


def test_요청하지_않은_태그는_점수에_영향이_없다():
    c = PlanConstraints(keywords=["조용한"])
    tagged = _place("tagged", 4.0, tags=["단체석"])
    plain = _place("plain", 4.0)
    assert score_place(tagged, c, None) == score_place(plain, c, None)
