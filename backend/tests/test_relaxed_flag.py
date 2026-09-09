"""완화 플래그는 실제로 완화 결과를 쓴 경우에만 선다."""
from __future__ import annotations

from app.adapters.map_service import get_map_service
from app.pipeline.agent import generate_course


async def test_완화로_나아진게_없으면_완화했다고_하지_않는다():
    result = await generate_course("성수동에서 저녁 데이트", get_map_service())
    assert len(result.timeline) >= 2
    assert result.relaxed is False
    # 완화하지 않았으니 사용자가 말한 조건 그대로 돌려준다
    assert result.constraints.companion == "데이트"


async def test_완화하지_않으면_안내문에_완화_문구가_없다():
    from app.main import _ai_reply
    from app.schemas import Course, Place, TimelineItem

    def _item(pid: str) -> TimelineItem:
        return TimelineItem(
            place=Place(id=pid, name=pid, lat=37.5, lng=127.0), travel_to_next=None
        )

    course = Course(id="c1", region="성수동", items=[_item("a"), _item("b")])
    text = _ai_reply(course, False, False)
    assert "완화" not in text
