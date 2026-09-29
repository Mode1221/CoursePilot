from app.pipeline.planner import score_place
from app.schemas import Place, PlanConstraints


def _place(name: str) -> Place:
    return Place(id=name, name=name, category="restaurant", lat=37.5, lng=127.0)


def test_large_party_prefers_group_seating():
    c = PlanConstraints(party_size=8)
    assert score_place(_place("단체룸 고깃집"), c, None) > score_place(_place("고깃집"), c, None)


def test_small_party_prefers_quiet_seating():
    c = PlanConstraints(party_size=2)
    assert score_place(_place("조용한 바"), c, None) > score_place(_place("바"), c, None)


def test_medium_party_is_neutral():
    c = PlanConstraints(party_size=3)
    assert score_place(_place("단체룸 고깃집"), c, None) == score_place(_place("고깃집"), c, None)


def test_no_party_size_is_neutral():
    c = PlanConstraints()
    assert score_place(_place("조용한 바"), c, None) == score_place(_place("바"), c, None)
