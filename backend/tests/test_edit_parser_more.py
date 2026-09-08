import pytest

from app.adapters.map_service import MockMapService
from app.pipeline.edit import LAST_INDEX, apply_edit, parse_edit
from app.schemas import Course, Place, TimelineItem


@pytest.mark.parametrize(
    ("text", "action", "index"),
    [
        ("3번 삭제", "remove", 2),
        ("2번 다른 곳으로", "replace", 1),
        ("마지막 장소 바꿔줘", "replace", LAST_INDEX),
        ("마지막 빼줘", "remove", LAST_INDEX),
        ("처음 거 빼줘", "remove", 0),
        ("두 번째 카페 말고 빵집으로 바꿔줘", "replace", 1),
    ],
)
def test_편집_표현을_폭넓게_인식한다(text: str, action: str, index: int):
    cmd = parse_edit(text)
    assert (cmd.action, cmd.index) == (action, index)


def test_편집이_아닌_문장은_none():
    assert parse_edit("성수동 3시간 코스").action == "none"


def _course() -> Course:
    items = [
        TimelineItem(place=Place(id=f"p{i}", name=f"장소{i}", lat=37.54, lng=127.05))
        for i in range(3)
    ]
    return Course(id="c1", title="t", region="성수동", items=items)


async def test_마지막_삭제는_끝_항목을_지운다():
    course = _course()
    items = await apply_edit(course, parse_edit("마지막 빼줘"), MockMapService())
    assert [it.place.id for it in items] == ["p0", "p1"]
