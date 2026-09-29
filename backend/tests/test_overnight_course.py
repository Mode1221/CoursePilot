from datetime import time

from app.adapters.map_service import MockMapService
from app.pipeline.validation import build_timeline
from app.schemas import Place, PlanConstraints


def _bars(n: int) -> list[Place]:
    return [
        Place(
            id=f"p{i}", name=f"P{i}", lat=37.54 + i * 0.001, lng=127.05,
            open_time=time(18, 0), close_time=time(2, 0),
        )
        for i in range(n)
    ]


async def test_자정을_넘는_코스도_생성된다():
    constraints = PlanConstraints(start_time=time(22, 0), end_time=time(1, 0))
    timeline = await build_timeline(_bars(3), constraints, MockMapService())
    assert len(timeline) >= 2  # 예전에는 종료 시각이 시작보다 앞서 즉시 중단됐다


async def test_같은_날_코스는_종료_시각을_지킨다():
    places = [
        Place(id=f"q{i}", name=f"Q{i}", lat=37.54 + i * 0.001, lng=127.05,
              open_time=time(9, 0), close_time=time(21, 0))
        for i in range(5)
    ]
    constraints = PlanConstraints(start_time=time(10, 0), end_time=time(13, 0))
    timeline = await build_timeline(places, constraints, MockMapService())
    assert timeline
    assert all(it.depart <= time(13, 0) for it in timeline)
