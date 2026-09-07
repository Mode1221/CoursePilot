import pytest

from app.adapters.map_service import MockMapService
from app.pipeline.planner import plan_course, score_place
from app.popularity import PopularityStore, popularity_store
from app.schemas import Place, PlanConstraints


def _p(pid, rating=4.0):
    return Place(id=pid, name=pid, category="카페", rating=rating, lat=37.5, lng=127.0)


def test_popularity_accumulates():
    ps = PopularityStore()
    ps.bump("a")
    ps.bump("a", weight=2)
    ps.bump_many(["b", "c"])
    scores = ps.scores(["a", "b", "z"])
    assert scores == {"a": 3, "b": 1, "z": 0}


def test_score_place_rewards_popularity():
    c = PlanConstraints()
    base = score_place(_p("x"), c, None, popularity=0.0)
    hot = score_place(_p("x"), c, None, popularity=1.0)
    assert hot > base


@pytest.mark.asyncio
async def test_planner_prefers_popular_place(monkeypatch):
    # 동일 평점 후보들 중 인기 높은 장소가 상위 채택되는지
    popularity_store._mem.clear()
    cands = await MockMapService().search_places("성수동", [], limit=6)
    popular = cands[-1]  # 임의 장소에 큰 인기 부여
    popularity_store.bump(popular.id, weight=100)

    c = PlanConstraints(region="성수동", duration_min=180)
    tl = await plan_course(cands, c, MockMapService())
    assert popular.id in {it.place.id for it in tl}
    popularity_store._mem.clear()
