from datetime import time

import pytest

from app.adapters.map_service import MockMapService
from app.pipeline.planner import (
    classify,
    course_score,
    desired_slots,
    plan_course,
    route_order,
    score_place,
)
from app.schemas import Place, PlanConstraints, Route, TimelineItem


def _p(pid, cat=None, rating=None, price=None, lat=37.5, lng=127.0):
    return Place(id=pid, name=pid, category=cat, rating=rating, price=price, lat=lat, lng=lng)


def test_classify():
    assert classify(_p("a", "한식")) == "meal"
    assert classify(_p("b", "카페")) == "cafe"
    assert classify(_p("c", "와인바")) == "bar"
    assert classify(_p("d", "갤러리")) == "activity"
    assert classify(_p("e", None)) == "activity"


def test_score_prefers_rating_and_keyword():
    c = PlanConstraints(keywords=["조용한"])
    high = _p("h", "조용한 카페", rating=4.8)
    low = _p("l", "시끌 카페", rating=3.0)
    assert score_place(high, c, None) > score_place(low, c, None)


def test_desired_slots_shapes():
    assert desired_slots(PlanConstraints(duration_min=120)) == ["meal", "cafe"]
    assert desired_slots(PlanConstraints(duration_min=180))[0] == "meal"
    assert len(desired_slots(PlanConstraints(duration_min=360))) == 4
    # 저녁대는 마지막이 bar
    assert desired_slots(PlanConstraints(duration_min=180, start_time=time(19, 0)))[-1] == "bar"


def test_route_order_minimizes_hops():
    a = _p("a", lat=0, lng=0)
    b = _p("b", lat=0, lng=0.001)
    c = _p("c", lat=0, lng=0.010)
    ordered = route_order([a, c, b])  # a 시작, 가까운 b 먼저
    assert [p.id for p in ordered] == ["a", "b", "c"]


def test_course_score_penalizes_travel():
    def _tl(travel):
        items = [
            TimelineItem(place=_p("a", "카페", rating=4.0),
                         travel_to_next=Route(from_place_id="a", to_place_id="b",
                                              mode="walk", duration_min=travel, distance_m=100)),
            TimelineItem(place=_p("b", "한식", rating=4.0)),
        ]
        return items
    assert course_score(_tl(5)) > course_score(_tl(30))


@pytest.mark.asyncio
async def test_plan_course_returns_diverse_quality_course():
    c = PlanConstraints(region="성수동", start_time=time(10, 0), duration_min=300)
    candidates = await MockMapService().search_places("성수동", [], limit=10)
    tl = await plan_course(candidates, c, MockMapService())
    assert len(tl) >= 3
    # 카테고리 다양성(카페만 있지 않음)
    cats = {classify(it.place) for it in tl}
    assert len(cats) >= 2
