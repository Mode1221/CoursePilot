"""삭제+추가 복합 명령은 교체로 읽는다."""
import pytest

from app.pipeline.edit import LAST_INDEX, parse_edit


@pytest.mark.parametrize(
    "text,index,keyword",
    [
        ("2번 지우고 카페 추가해줘", 1, "카페"),
        ("첫번째 빼고 술집 넣어줘", 0, "술집"),
        ("마지막 빼고 카페 넣어줘", LAST_INDEX, "카페"),
    ],
)
def test_그_자리를_말한_성격으로_바꾼다(text, index, keyword):
    cmd = parse_edit(text)
    assert (cmd.action, cmd.index, cmd.keyword) == ("replace", index, keyword)


def test_성격을_말하지_않으면_삭제로_둔다():
    assert parse_edit("2번 지우고 하나 더 넣어줘").action == "remove"


@pytest.mark.parametrize(
    "text,action",
    [
        ("첫번째 빼줘", "remove"),
        ("카페 하나 추가해줘", "add"),
        ("두번째를 카페로 바꿔줘", "replace"),
    ],
)
def test_단일_명령은_그대로다(text, action):
    assert parse_edit(text).action == action
