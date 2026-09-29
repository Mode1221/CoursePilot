import pytest

from app.pipeline.edit import EditCommand, apply_edit
from app.schemas import Course, Place, Route, TimelineItem


class FakeMapService:
    async def search_places(self, region, keywords, limit=10):
        return [
            Place(id="new-r", name="새 식당", category="restaurant", lat=37.5, lng=127.0),
            Place(id="new-c", name="새 카페", category="cafe", lat=37.5, lng=127.0),
        ]

    async def get_route(self, origin, dest, mode):
        return Route(
            from_place_id=origin.id,
            to_place_id=dest.id,
            mode=mode,
            duration_min=10,
            distance_m=500,
        )


def _course() -> Course:
    return Course(
        id="c1",
        title="t",
        items=[
            TimelineItem(place=Place(id="r", name="식당", category="restaurant", lat=37.5, lng=127.0)),
            TimelineItem(place=Place(id="c", name="카페", category="cafe", lat=37.5, lng=127.0)),
        ],
    )


@pytest.mark.asyncio
async def test_replace_keeps_category():
    items = await apply_edit(_course(), EditCommand(action="replace", index=1), FakeMapService())
    assert items[1].place.id == "new-c"
