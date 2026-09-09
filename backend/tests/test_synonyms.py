"""같은 뜻 다른 말도 같은 조건으로 읽는다."""
import pytest

from app.pipeline.decomposition import SYNONYMS, normalize_synonyms, parse_constraints


@pytest.mark.parametrize(
    "text,keyword",
    [
        ("강아지랑 갈 만한 카페", "반려동물"),
        ("댕댕이 동반 가능한 곳", "반려동물"),
        ("애견 동반 식당", "반려동물"),
        ("노트북 하기 좋은 카페", "콘센트"),
        ("카공하기 좋은 데", "콘센트"),
    ],
)
def test_동의어를_표준어로_읽는다(text, keyword):
    assert keyword in parse_constraints(text).keywords


def test_이미_표준어인_말은_그대로다():
    assert normalize_synonyms("반려동물 동반") == "반려동물 동반"


def test_사전에_있는_말은_건드리지_않는다():
    # 유모차·휠체어는 그 자체로 검색어이자 동행유형 판정에 쓰인다
    c = parse_constraints("유모차 끌고 갈 카페")
    assert "유모차" in c.keywords and c.companion == "가족"
    assert "휠체어" in parse_constraints("휠체어 접근 되는 곳").keywords


def test_치환표는_서로_다른_표기만_담는다():
    assert all(word != standard for word, standard in SYNONYMS.items())
