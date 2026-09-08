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
    # 최근 즉시 누적이라 감쇠 거의 없음 → 근사 비교
    assert abs(scores["a"] - 3.0) < 0.01
    assert abs(scores["b"] - 1.0) < 0.01
    assert scores["z"] == 0.0


def test_popularity_time_decay():
    import app.popularity as pop

    ps = pop.PopularityStore()
    ps.bump("a", weight=4)
    # 마지막 갱신 시각을 한 반감기 전으로 위조
    score, ts = ps._mem["a"]
    ps._mem["a"] = (score, ts - pop._HALF_LIFE_SEC)
    assert abs(ps.scores(["a"])["a"] - 2.0) < 0.05  # 반감


def test_score_place_rewards_popularity():
    c = PlanConstraints()
    base = score_place(_p("x"), c, None, popularity=0.0)
    hot = score_place(_p("x"), c, None, popularity=1.0)
    assert hot > base


@pytest.mark.asyncio
async def test_planner_prefers_popular_place(monkeypatch):
    # 동일 평점 후보들 중 인기 높은 장소가 상위 채택되는지
    from app.cooccurrence import cooccurrence_store

    popularity_store._mem.clear()
    cooccurrence_store._mem.clear()
    cands = await MockMapService().search_places("성수동", [], limit=6)
    # 낮 시간대에 영업하는 후보로 지정(심야 술집은 기본 시작 시각에 영업 전)
    popular = next(p for p in cands if p.category != "bar")
    popularity_store.bump(popular.id, weight=100)

    c = PlanConstraints(region="성수동", duration_min=180)
    tl = await plan_course(cands, c, MockMapService())
    assert popular.id in {it.place.id for it in tl}
    popularity_store._mem.clear()


def test_bump_many_는_인메모리에서도_동일하게_누적된다():
    from app.popularity import PopularityStore

    store = PopularityStore()
    store.bump_many(["a", "b"], weight=2)
    scores = store.scores(["a", "b", "c"])
    assert scores["a"] == pytest.approx(2.0)
    assert scores["b"] == pytest.approx(2.0)
    assert scores["c"] == 0.0


def test_빈_목록은_아무것도_하지_않는다():
    from app.popularity import PopularityStore

    store = PopularityStore()
    store.bump_many([])
    assert store.scores([]) == {}
