"""부족할 때 왜 부족한지 알려준다."""
from __future__ import annotations

from datetime import time

from app.main import _ai_reply
from app.schemas import Course, PlanConstraints


def _empty() -> Course:
    return Course(id="c1", region="성수동")


def test_심야_요청은_영업시간을_짚어준다():
    text = _ai_reply(
        _empty(), False, True, constraints=PlanConstraints(start_time=time(3, 0))
    )
    assert "문 연 곳" in text and "3시" in text


def test_예산이_빡빡하면_예산을_짚어준다():
    text = _ai_reply(
        _empty(), False, True, constraints=PlanConstraints(budget_max=1000)
    )
    assert "1,000원" in text and "예산" in text

    man = _ai_reply(
        _empty(), False, True, constraints=PlanConstraints(budget_max=30000)
    )
    assert "3만원" in man


def test_이유를_모르면_지역_시간_변경을_제안한다():
    text = _ai_reply(_empty(), False, True, constraints=PlanConstraints(region="성수동"))
    assert "지역이나 시간" in text


def test_일부만_찾았으면_개수를_알려준다():
    from app.schemas import Place, TimelineItem

    course = Course(
        id="c2",
        items=[
            TimelineItem(place=Place(id=f"p{i}", name=f"p{i}", lat=37.5, lng=127.0))
            for i in range(2)
        ],
    )
    text = _ai_reply(course, False, True, constraints=PlanConstraints(stop_count=5))
    assert "2곳까지만" in text
