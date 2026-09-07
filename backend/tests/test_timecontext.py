from datetime import time as dtime

import pytest

from app.adapters.map_service import MockMapService
from app.pipeline.planner import plan_course, score_place
from app.schemas import PlanConstraints
from app.timecontext import TimeContextStore, daypart_of, time_context_store


def test_daypart_buckets():
    assert daypart_of(9) == "morning"
    assert daypart_of(14) == "afternoon"
    assert daypart_of(20) == "evening"


def test_time_context_scores_by_daypart():
    ts = TimeContextStore()
    ts.bump("a", "evening", weight=3)
    ts.bump("a", "morning")
    assert ts.scores(["a"], "evening")["a"] == 3.0
    assert ts.scores(["a"], "morning")["a"] == 1.0
    assert ts.scores(["a"], "afternoon")["a"] == 0.0


def test_score_place_rewards_context():
    from app.schemas import Place

    c = PlanConstraints()
    p = Place(id="x", name="x", category="카페", rating=4.0, lat=37.5, lng=127.0)
    lo = score_place(p, c, None, context_pop=0.0)
    hi = score_place(p, c, None, context_pop=1.0)
    assert hi > lo


@pytest.mark.asyncio
async def test_planner_prefers_context_match(monkeypatch):
    from app.cooccurrence import cooccurrence_store
    from app.popularity import popularity_store

    time_context_store._mem.clear()
    cooccurrence_store._mem.clear()
    popularity_store._mem.clear()
    cands = await MockMapService().search_places("성수동", [], limit=6)
    target = cands[-1]
    # 저녁 시간대에 강하게 채택된 장소
    time_context_store.bump(target.id, "evening", weight=100)

    c = PlanConstraints(region="성수동", duration_min=180, start_time=dtime(19, 0))
    tl = await plan_course(cands, c, MockMapService())
    assert target.id in {it.place.id for it in tl}
    time_context_store._mem.clear()
