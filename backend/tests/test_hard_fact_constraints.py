"""동반 조건(반려동물·단체석 등)은 감점이 아니라 제외로 처리한다."""
from datetime import time

import pytest

from app.adapters.map_service import MockMapService
from app.pipeline.planner import plan_course, required_fact_tags
from app.schemas import Place, PlanConstraints


def _place(pid, caution=(), fact=()) -> Place:
    return Place(
        id=pid,
        name=pid,
        category="음식점>한식",
        lat=37.54,
        lng=127.05,
        price=15000,
        open_time=time(9, 0),
        close_time=time(23, 0),
        caution_tags=list(caution),
        fact_tags=list(fact),
    )


@pytest.mark.parametrize(
    "keywords,expected",
    [
        (["반려동물"], ["반려동물"]),
        (["강아지"], ["반려동물"]),
        (["단체석"], ["단체석"]),
        (["조용한"], []),
    ],
)
def test_필수_축을_뽑는다(keywords, expected):
    assert required_fact_tags(PlanConstraints(keywords=keywords)) == expected


async def test_불가로_확인된_곳은_후보에서_뺀다():
    constraints = PlanConstraints(keywords=["반려동물"], start_time=time(12, 0))
    candidates = [_place("no", caution=["반려동물"]), _place("ok", fact=["반려동물"])]
    timeline = await plan_course(candidates, constraints, MockMapService())
    assert [it.place.id for it in timeline] == ["ok"]


async def test_전부_불가면_원래_후보를_지킨다():
    constraints = PlanConstraints(keywords=["반려동물"], start_time=time(12, 0))
    candidates = [_place("a", caution=["반려동물"]), _place("b", caution=["반려동물"])]
    timeline = await plan_course(candidates, constraints, MockMapService())
    assert timeline  # 아무 코스도 못 주는 것보다는 낫다


async def test_요청하지_않은_축은_거르지_않는다():
    constraints = PlanConstraints(keywords=["조용한"], start_time=time(12, 0))
    candidates = [_place("a", caution=["반려동물"])]
    timeline = await plan_course(candidates, constraints, MockMapService())
    assert [it.place.id for it in timeline] == ["a"]
