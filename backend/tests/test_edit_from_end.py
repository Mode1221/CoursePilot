"""뒤에서 센 자리 지목과, '순서'라는 말 없는 맞바꾸기."""
import pytest

from app.adapters.map_service import MockMapService
from app.pipeline.edit import apply_edit, parse_edit
from app.schemas import Course, Place, TimelineItem


def _course(n: int) -> Course:
    items = [
        TimelineItem(
            place=Place(id=f"p{i}", name=f"장소{i}", category="카페", address="서울",
                        lat=37.54 + i / 1000, lng=127.05 + i / 1000)
        )
        for i in range(n)
    ]
    return Course(id="c1", items=items)


def test_끝에서_센_자리를_한_곳으로_읽는다():
    from app.pipeline.edit import FROM_END_BASE, LAST_INDEX

    # '마지막'과 '두 번째'로 쪼개지 않고 한 자리로 읽는다
    assert parse_edit("마지막에서 두번째 삭제").index == FROM_END_BASE - 2
    assert parse_edit("끝에서 두번째 빼줘").index == FROM_END_BASE - 2
    assert parse_edit("마지막 삭제").index == LAST_INDEX


@pytest.mark.parametrize(
    "text,남는이름",
    [
        ("마지막 삭제", ["장소0", "장소1", "장소2"]),
        ("마지막에서 두번째 삭제", ["장소0", "장소1", "장소3"]),
        ("끝에서 세번째 지워", ["장소0", "장소2", "장소3"]),
    ],
)
async def test_끝에서_센_자리를_지운다(text, 남는이름):
    course = _course(4)
    items = await apply_edit(course, parse_edit(text), MockMapService())
    assert [it.place.name for it in items] == 남는이름


async def test_순서라는_말_없이도_두_자리를_맞바꾼다():
    course = _course(3)
    items = await apply_edit(course, parse_edit("1번과 3번 바꿔"), MockMapService())
    assert [it.place.name for it in items] == ["장소2", "장소1", "장소0"]


async def test_바꿀_성격을_말하면_교체로_읽는다():
    cmd = parse_edit("두번째를 카페로 바꿔줘")
    assert cmd.action == "replace"
    assert cmd.index == 1
