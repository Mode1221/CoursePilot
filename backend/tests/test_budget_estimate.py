"""추정가 예산 판정: 카테고리 평균의 오차를 여유폭으로 흡수한다."""
from datetime import time

from app.adapters.map_service import MockMapService
from app.pipeline.validation import ESTIMATE_SLACK, build_timeline
from app.schemas import Place, PlanConstraints


def _place(pid: str, price: int, estimated: bool) -> Place:
    return Place(
        id=pid,
        name=pid,
        category="음식점>한식",
        lat=37.54,
        lng=127.05,
        price=price,
        price_estimated=estimated,
        open_time=time(9, 0),
        close_time=time(23, 0),
    )


async def _plan(places, budget):
    constraints = PlanConstraints(start_time=time(12, 0), budget_max=budget)
    return await build_timeline(places, constraints, MockMapService())


async def test_추정가는_여유폭_안이면_통과한다():
    # 20,000원 예산의 여유폭은 24,000원. 그보다 비싸면 추정가라도 자른다.
    over = _place("est", 25_000, True)
    timeline = await _plan([over], 20_000)
    assert [i.place.id for i in timeline] == []

    within = _place("est2", 23_000, True)
    timeline = await _plan([within], 20_000)
    assert [i.place.id for i in timeline] == ["est2"]


async def test_실제_가격은_여유_없이_자른다():
    exact = _place("real", 23_000, False)
    assert await _plan([exact], 20_000) == []


async def test_여유폭은_1_2배():
    assert ESTIMATE_SLACK == 1.2


async def test_예산이_없으면_아무것도_자르지_않는다():
    timeline = await _plan([_place("p", 100_000, True)], None)
    assert [i.place.id for i in timeline] == ["p"]
