"""동사 없이 성격만 말한 교체("여기 말고 다른 술집")."""
import pytest

from app.pipeline.edit import MATCH_INDEX, parse_edit


def test_카테고리를_말하면_그_자리를_바꾼다():
    cmd = parse_edit("여기 말고 다른 술집")
    assert cmd.action == "replace" and cmd.keyword == "술집" and cmd.index == MATCH_INDEX


def test_자리를_집으면_그_자리를_바꾼다():
    cmd = parse_edit("두번째는 다른 카페로")
    assert (cmd.action, cmd.index, cmd.keyword) == ("replace", 1, "카페")


def test_성격도_자리도_없으면_되묻는다():
    assert parse_edit("다른 데 없어?").action in ("clarify", "none")


@pytest.mark.parametrize(
    "text,action",
    [
        ("첫번째 빼줘", "remove"),
        ("카페 하나 추가해줘", "add"),
        ("두번째를 카페로 바꿔줘", "replace"),
        ("순서 바꿔줘", "reorder"),
        ("다 지워", "clear"),
    ],
)
def test_기존_명령은_그대로_동작한다(text, action):
    assert parse_edit(text).action == action


def test_다른_곳은_성격으로_보지_않는다():
    # "다른 곳/데/장소"는 성격이 아니라 그냥 교체 요청이다
    assert parse_edit("다른 곳으로 바꿔줘").keyword == ""
