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


def test_지워_치워도_삭제로_인식한다():
    assert parse_edit("세 번째 지워").action == "remove"
    assert parse_edit("세 번째 지워").index == 2
    assert parse_edit("첫번째 치워줘").action == "remove"


def test_순서_바꿔줘는_순서_재배치로_인식한다():
    assert parse_edit("순서 바꿔줘").action == "reorder"
    assert parse_edit("동선 좀 최적화해줘").action == "reorder"
    # 카테고리(bar)로 오인하지 않는다
    assert parse_edit("순서 바꿔줘").match == ""


def test_한글자_카테고리는_단독일_때만_인식한다():
    assert parse_edit("바 빼줘").match == "bar"
