from app.pipeline.planner import score_place
from app.schemas import Place, PlanConstraints


def _p(pid, rating):
    return Place(id=pid, name=pid, category="카페", rating=rating, lat=37.5, lng=127.0)


def test_cold_start_boosts_external_rating():
    c = PlanConstraints()
    # 콜드스타트에서는 외부 평점에 추가 의존 → 고평점 장소 점수 상승
    warm = score_place(_p("x", 5.0), c, None, cold_start=False)
    cold = score_place(_p("x", 5.0), c, None, cold_start=True)
    assert cold > warm


def test_cold_start_ranks_by_external_rating():
    c = PlanConstraints()
    hi = score_place(_p("hi", 5.0), c, None, cold_start=True)
    lo = score_place(_p("lo", 3.0), c, None, cold_start=True)
    assert hi > lo


def test_no_boost_without_external_rating():
    c = PlanConstraints()
    p = Place(id="n", name="n", category="카페", rating=None, lat=37.5, lng=127.0)
    assert score_place(p, c, None, cold_start=True) == score_place(p, c, None, cold_start=False)
