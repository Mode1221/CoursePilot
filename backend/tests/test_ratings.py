import pytest
from fastapi.testclient import TestClient

from app.adapters.map_service import MockMapService
from app.main import api
from app.pipeline.planner import plan_course, score_place
from app.ratings import RatingStore, rating_store
from app.schemas import Place, PlanConstraints


def _p(pid, rating=4.0):
    return Place(id=pid, name=pid, category="카페", rating=rating, lat=37.5, lng=127.0)


def test_rating_store_average():
    rs = RatingStore()
    rs.submit("a", 5)
    rs.submit("a", 3)
    rs.submit("b", 4)
    assert rs.averages(["a", "b", "z"]) == {"a": 4.0, "b": 4.0}


def test_self_rating_blends_into_score():
    c = PlanConstraints()
    low_ext = _p("x", rating=2.0)
    # 외부 별점 낮아도 자체 별점 높으면 점수 상승
    base = score_place(low_ext, c, None)
    boosted = score_place(low_ext, c, None, self_rating=5.0)
    assert boosted > base


def test_rating_endpoint_validates():
    client = TestClient(api)
    assert client.post("/places/p1/rating", json={"stars": 5}).status_code == 200
    assert client.post("/places/p1/rating", json={"stars": 6}).status_code == 422


@pytest.mark.asyncio
async def test_planner_uses_self_rating():
    rating_store._mem.clear()
    cands = await MockMapService().search_places("성수동", [], limit=6)
    # 낮 시간대에 영업하는 후보로 지정(심야 술집은 기본 시작 시각에 영업 전)
    target = next(p for p in cands if p.category != "bar")
    for _ in range(5):
        rating_store.submit(target.id, 5)
    c = PlanConstraints(region="성수동", duration_min=180)
    tl = await plan_course(cands, c, MockMapService())
    assert target.id in {it.place.id for it in tl}
    rating_store._mem.clear()
