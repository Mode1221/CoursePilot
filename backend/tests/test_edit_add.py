"""장소 추가 편집 명령("카페 하나 추가해줘")."""
from app.adapters.map_service import MockMapService
from app.pipeline.edit import apply_edit, parse_edit
from app.schemas import Course, Place, TimelineItem


def _course() -> Course:
    item = TimelineItem(place=Place(id="p1", name="기존", category="restaurant", lat=37.5, lng=127.0))
    return Course(id="c1", region="성수동", items=[item])


def test_추가_명령을_파싱한다():
    cmd = parse_edit("카페 하나 추가해줘")
    assert cmd.action == "add"
    assert cmd.match == "cafe"


def test_교체_명령은_추가로_보지_않는다():
    assert parse_edit("두 번째 카페 다른 곳으로 바꿔줘").action == "replace"


def test_카테고리가_없으면_추가로_보지_않는다():
    assert parse_edit("하나 더 추가해줘").action == "none"


async def test_요청한_성격의_장소가_뒤에_붙는다():
    course = _course()
    items = await apply_edit(course, parse_edit("카페 하나 추가해줘"), MockMapService())
    assert len(items) == 2
    assert items[1].place.category == "cafe"
    assert items[0].place.id == "p1"
