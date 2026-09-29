"""대안 지명·상황 키워드."""
import pytest

from app.pipeline.decomposition import parse_constraints


@pytest.mark.parametrize(
    "text,expected",
    [
        ("성수 아니면 연남 둘 중에 아무데나", "성수"),
        ("홍대나 합정", "홍대"),
        ("강남 아니면 홍대", "강남"),
        ("연남에서 저녁", "연남"),
    ],
)
def test_먼저_말한_지역을_쓴다(text, expected):
    assert parse_constraints(text).region == expected


@pytest.mark.parametrize(
    "text,keyword",
    [
        ("애들이랑 유모차 끌고 갈 카페", "유모차"),
        ("생일파티 케이크 되는 곳", "케이크"),
        ("다이어트 중이라 가벼운 걸로", "가벼운"),
        ("해장 되는 데", "해장"),
    ],
)
def test_상황_표현을_검색어로_쓴다(text, keyword):
    assert keyword in parse_constraints(text).keywords


def test_지명이_없으면_비운다():
    assert parse_constraints("맛있는 거 먹고 싶어").region is None
