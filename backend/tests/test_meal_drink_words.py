"""끼니·술자리 표현."""
import pytest

from app.pipeline.decomposition import parse_constraints


@pytest.mark.parametrize(
    "text,keyword",
    [
        ("성수동에서 밥 먹고 커피", "밥"),
        ("홍대 술 한잔", "술집"),
        ("이태원에서 술만", "술집"),
        ("한잔하러 가자", "술집"),
        ("저녁식사 하기 좋은 곳", "저녁식사"),
    ],
)
def test_검색어로_읽는다(text, keyword):
    assert keyword in parse_constraints(text).keywords


def test_예술은_술집으로_읽지_않는다():
    assert "술집" not in parse_constraints("성수에서 예술 전시 보고 싶어").keywords


def test_밥과_커피를_함께_읽는다():
    keywords = parse_constraints("성수동에서 밥 먹고 커피").keywords
    assert "밥" in keywords and "커피" in keywords
