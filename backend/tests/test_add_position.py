"""추가 위치 지정("맨 앞에 카페 넣어줘")."""
from __future__ import annotations

from app.adapters.map_service import MockMapService
from app.pipeline.edit import apply_edit, parse_edit
from app.schemas import Course, Place, TimelineItem


def _course() -> Course:
    places = [
        Place(id=f"a{i}", name=f"기존{i}", category="restaurant", lat=37.5, lng=127.0)
        for i in range(3)
    ]
    return Course(id="c1", region="성수동", items=[TimelineItem(place=p) for p in places])


async def test_맨_앞에_넣는다():
    cmd = parse_edit("맨 앞에 카페 하나 넣어줘")
    assert cmd.action == "add" and cmd.index == 0
    items = await apply_edit(_course(), cmd, MockMapService())
    assert len(items) == 4
    assert items[0].place.id not in {"a0", "a1", "a2"}


async def test_지목한_자리_앞에_넣는다():
    cmd = parse_edit("3번째 앞에 카페 넣어줘")
    assert cmd.index == 2
    items = await apply_edit(_course(), cmd, MockMapService())
    assert [it.place.id for it in items[:2]] == ["a0", "a1"]
    assert items[2].place.id not in {"a0", "a1", "a2"}


async def test_위치를_말하지_않으면_맨_뒤():
    cmd = parse_edit("카페 하나 추가해줘")
    assert cmd.index == -1
    items = await apply_edit(_course(), cmd, MockMapService())
    assert [it.place.id for it in items[:3]] == ["a0", "a1", "a2"]
    assert len(items) == 4
