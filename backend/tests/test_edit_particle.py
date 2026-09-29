"""교체 표현의 조사 변형("곳으로")."""
import pytest

from app.pipeline.edit import LAST_INDEX, parse_edit


@pytest.mark.parametrize(
    "text,index,keyword",
    [
        ("마지막을 가까운 곳으로", LAST_INDEX, "가까운"),
        ("첫번째를 좀 더 조용한 데로", 0, "조용한"),
        ("2번째 평점 높은 데로", 1, "평점 높은"),
        ("세번째를 저렴한 장소로", 2, "저렴한"),
    ],
)
def test_조사가_붙어도_교체로_읽는다(text, index, keyword):
    cmd = parse_edit(text)
    assert (cmd.action, cmd.index, cmd.keyword) == ("replace", index, keyword)


def test_기존_표현도_그대로_동작한다():
    assert parse_edit("두번째를 카페로 바꿔줘").action == "replace"
    assert parse_edit("첫번째 빼줘").action == "remove"
