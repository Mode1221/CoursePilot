"""질문 유형별 답변: 사실 태그·비용·요약."""
from datetime import time

import pytest

from app.main import _course_answer
from app.schemas import Course, Place, TimelineItem


def _course(**place_kw) -> Course:
    base = {"id": "p1", "name": "성수커피", "lat": 37.5, "lng": 127.0}
    place = Place(**{**base, **place_kw})
    return Course(id="c", items=[TimelineItem(place=place, arrive=time(13, 0), depart=time(14, 0))])


def test_주차를_물으면_주차로_답한다():
    assert "주차 가능" in _course_answer(_course(fact_tags=["주차"]), "여기 주차 되나요?")


def test_어려운_축은_주의로_답한다():
    answer = _course_answer(_course(name="성수식당", caution_tags=["단체석"]), "단체 가능해?")
    assert "어려울 수 있어요" in answer


def test_모르면_모른다고_답한다():
    answer = _course_answer(_course(), "반려동물 되나요")
    assert "확인되지 않았" in answer


def test_조사를_받침에_맞춘다():
    with_batchim = _course_answer(_course(name="성수식당", fact_tags=["주차"]), "주차 되나요")
    without = _course_answer(_course(name="성수커피", fact_tags=["주차"]), "주차 되나요")
    assert "성수식당은" in with_batchim and "성수커피는" in without


def test_비용을_물으면_합계로_답한다():
    answer = _course_answer(_course(price=8000), "비용 얼마야")
    assert "8,000원" in answer


def test_추정가가_섞이면_밝힌다():
    answer = _course_answer(_course(price=8000, price_estimated=True), "얼마 들어?")
    assert "추정 포함" in answer


def test_가격을_모르면_모른다고_답한다():
    assert "계산하기 어려워요" in _course_answer(_course(), "얼마야")


@pytest.mark.parametrize("question", ["얼마나 걸려", "몇 시에 끝나", "1번 어디야"])
def test_그_외에는_코스_요약으로_답한다(question):
    assert "지금 코스는" in _course_answer(_course(), question)
