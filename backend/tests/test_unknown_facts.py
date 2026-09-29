"""모으지 않는 정보는 요약으로 얼버무리지 않는다."""
from datetime import time

import pytest

from app.answers import course_answer
from app.schemas import Course, Place, TimelineItem


def _course(**kw) -> Course:
    base = {"id": "p1", "name": "성수커피", "lat": 37.5, "lng": 127.0}
    place = Place(**{**base, **kw})
    return Course(id="c", items=[TimelineItem(place=place, arrive=time(13, 0), depart=time(14, 0))])


@pytest.mark.parametrize(
    "question,tag",
    [
        ("화장실 있어?", "화장실"),
        ("와이파이 되나요", "와이파이"),
        ("흡연 가능?", "흡연"),
        ("콜키지 되나요", "콜키지"),
        ("포장 되나요", "배달"),
    ],
)
def test_모으지_않는_정보는_그렇다고_답한다(question, tag):
    answer = course_answer(_course(), question)
    assert tag in answer and "아직 모으지 않아요" in answer


def test_모으는_정보는_그대로_답한다():
    assert "주차 가능" in course_answer(_course(fact_tags=["주차"]), "주차 되나요")


def test_다른_질문은_영향받지_않는다():
    assert "8,000원" in course_answer(_course(price=8000), "얼마야")
