"""여러 자리 삭제와 '남기고' 표현 보호."""
from __future__ import annotations

from app.adapters.map_service import MockMapService
from app.pipeline.edit import apply_edit, parse_edit
from app.schemas import Course, Place, TimelineItem


def _course() -> Course:
    places = [
        Place(id=f"p{i}", name=f"장소{i}", category="cafe", lat=37.5 + i * 0.001, lng=127.0)
        for i in range(4)
    ]
    return Course(id="c1", region="성수동", items=[TimelineItem(place=p) for p in places])


async def test_두_자리를_한_번에_지운다():
    cmd = parse_edit("2번째랑 3번째 빼줘")
    assert cmd.indexes == [1, 2]
    items = await apply_edit(_course(), cmd, MockMapService())
    assert [it.place.id for it in items] == ["p0", "p3"]


async def test_한_자리만_지목하면_기존대로():
    items = await apply_edit(_course(), parse_edit("2번째 빼줘"), MockMapService())
    assert [it.place.id for it in items] == ["p0", "p2", "p3"]


async def test_남기고_표현은_지목한_자리만_남긴다():
    """예전엔 되물었다 — 무엇을 남길지 말했으니 그대로 한다(전부 비우지 않는다)."""
    course = _course()
    cmd = parse_edit("첫번째만 남기고 다 지워")
    assert cmd.action == "keep"
    items = await apply_edit(course, cmd, MockMapService())
    assert [it.place.id for it in items] == [course.items[0].place.id]
    two = await apply_edit(course, parse_edit("1번이랑 3번만 남기고 다 빼"), MockMapService())
    assert {it.place.id for it in two} == {course.items[0].place.id, course.items[2].place.id}


def test_무엇을_남길지_없으면_되묻는다():
    assert parse_edit("남기고 다 지워").action == "clarify"


async def test_전체_삭제는_그대로_동작한다():
    assert parse_edit("다 지워").action == "clear"
    assert await apply_edit(_course(), parse_edit("다 지워"), MockMapService()) == []
