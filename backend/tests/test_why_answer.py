"""추천 이유 질문에는 근거로 답한다."""
from datetime import date, time, timedelta

import pytest

from app.answers import course_answer
from app.schemas import Course, Place, TimelineItem


def _course(**kw) -> Course:
    base = {"id": "p1", "name": "성수커피", "lat": 37.5, "lng": 127.0}
    place = Place(**{**base, **kw})
    return Course(id="c", items=[TimelineItem(place=place, arrive=time(13, 0), depart=time(14, 0))])


@pytest.mark.parametrize("question", ["여기 왜 골랐어?", "이유가 뭐야", "무슨 근거로 고른 거야"])
def test_근거를_답한다(question):
    course = _course(rating=4.6, rating_count=500)
    assert "평점 4.6" in course_answer(course, question)


def test_업력도_근거로_든다():
    course = _course(opened_on=date.today() - timedelta(days=365 * 9))
    assert "년째 영업 중" in course_answer(course, "왜 이 집이야?")


def test_근거가_없으면_그렇게_말한다():
    assert "이동 동선과 시간대" in course_answer(_course(), "왜 골랐어?")


def test_다른_질문은_영향받지_않는다():
    assert "8,000원" in course_answer(_course(price=8000), "얼마야")
