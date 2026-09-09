"""흔한 오타도 검색어로 읽는다."""
import pytest

from app.pipeline.decomposition import TYPO_FIXES, normalize_typos, parse_constraints


@pytest.mark.parametrize(
    "text,keyword",
    [
        ("성수동 카폐 추천", "카페"),
        ("홍대 까페", "카페"),
        ("연남 브런취", "브런치"),
        ("성수 디져트", "디저트"),
        ("을지로 술찝", "술집"),
    ],
)
def test_오타를_교정해_읽는다(text, keyword):
    assert keyword in parse_constraints(text).keywords


def test_정상_표기는_그대로다():
    assert normalize_typos("성수동 카페") == "성수동 카페"


def test_지역은_영향을_받지_않는다():
    assert parse_constraints("성수동 카폐").region == "성수동"


def test_교정표는_서로_다른_표기만_담는다():
    assert all(wrong != right for wrong, right in TYPO_FIXES.items())
