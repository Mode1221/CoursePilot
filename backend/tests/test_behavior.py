from app.behavior import BehaviorStore
from app.pipeline.planner import score_place
from app.schemas import Place, PlanConstraints


def _p(cat):
    return Place(id=cat, name=cat, category=cat, rating=4.0, lat=37.5, lng=127.0)


def test_top_categories_threshold():
    bs = BehaviorStore()
    bs.bump("u1", ["cafe", "cafe"])   # cafe 2
    bs.bump("u1", ["bar"])            # bar 1 (임계 미만)
    assert bs.top_categories("u1") == ["cafe"]
    assert bs.top_categories("") == []


def test_score_place_rewards_behavior_match():
    c = PlanConstraints()
    p = _p("카페")  # classify → cafe
    base = score_place(p, c, {})
    hit = score_place(p, c, {"behavior_cats": ["cafe"]})
    assert hit > base
