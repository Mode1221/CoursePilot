from app.pipeline.agent import MIN_VALID, _min_valid
from app.schemas import PlanConstraints


def test_default_requires_three():
    assert _min_valid(PlanConstraints()) == MIN_VALID


def test_requested_two_stops_is_enough():
    assert _min_valid(PlanConstraints(stop_count=2)) == 2


def test_more_stops_still_capped_at_default():
    assert _min_valid(PlanConstraints(stop_count=4)) == MIN_VALID
