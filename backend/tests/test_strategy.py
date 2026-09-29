import pytest

from app.adapters.map_service import MockMapService
from app.pipeline.planner import plan_course
from app.schemas import PlanConstraints
from app.strategy import StrategyStore, strategy_store


def test_strategy_counts():
    ss = StrategyStore()
    ss.bump("template")
    ss.bump("template")
    ss.bump("route")
    assert ss.counts() == {"template": 2, "route": 1}


@pytest.mark.asyncio
async def test_plan_course_logs_winning_strategy():
    strategy_store._mem.clear()
    cands = await MockMapService().search_places("성수동", [], limit=6)
    c = PlanConstraints(region="성수동", duration_min=180)
    await plan_course(cands, c, MockMapService())
    counts = strategy_store.counts()
    assert sum(counts.values()) == 1  # 채택된 전략 하나가 기록됨
    assert set(counts) <= {"template", "route", "sequence", "score"}
    strategy_store._mem.clear()
