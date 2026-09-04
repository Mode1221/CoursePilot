import pytest

from app.adapters.map_service import MockMapService
from app.pipeline.edit import apply_edit, parse_edit
from app.schemas import Course, Place, TimelineItem


def test_parse_replace():
    cmd = parse_edit("두 번째 카페 말고 빵집으로 바꿔줘")
    assert cmd.action == "replace"
    assert cmd.index == 1
    assert cmd.keyword == "빵집"


def test_parse_remove_numeric():
    cmd = parse_edit("3번째 장소 빼줘")
    assert cmd.action == "remove"
    assert cmd.index == 2


def test_parse_none():
    assert parse_edit("성수동 3시간 코스 만들어줘").action == "none"


def _course():
    items = [
        TimelineItem(place=Place(id=f"x{i}", name=f"p{i}", lat=37.5 + i * 0.001, lng=127.0 + i * 0.001))
        for i in range(3)
    ]
    return Course(id="c", title="t", region="성수동", items=items)


@pytest.mark.asyncio
async def test_apply_remove_recomputes():
    course = _course()
    items = await apply_edit(course, parse_edit("2번째 빼줘"), MockMapService())
    assert len(items) == 2
    assert items[0].arrive is not None
    assert items[-1].travel_to_next is None


@pytest.mark.asyncio
async def test_apply_replace_swaps_place():
    course = _course()
    before = course.items[1].place.id
    items = await apply_edit(course, parse_edit("두 번째 빵집으로 바꿔줘"), MockMapService())
    assert len(items) == 3
    assert items[1].place.id != before
