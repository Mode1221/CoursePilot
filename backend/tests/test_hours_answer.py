"""영업시간 질문에는 장소별 시간으로 답한다."""
from datetime import time

import pytest

from app.answers import course_answer
from app.schemas import Course, Place, TimelineItem


def _course(*places: Place) -> Course:
    return Course(id="c", items=[TimelineItem(place=p) for p in places])


def _place(name, **kw) -> Place:
    return Place(**{"id": name, "name": name, "lat": 37.5, "lng": 127.0, **kw})


@pytest.mark.parametrize("question", ["몇 시까지 해?", "영업시간 알려줘", "문 닫는 시간"])
def test_영업시간을_답한다(question):
    course = _course(_place("성수커피", open_time=time(10, 0), close_time=time(22, 0)))
    assert "10:00~22:00" in course_answer(course, question)


def test_확인하지_못한_곳은_그렇게_말한다():
    course = _course(_place("성수식당", hours_unverified=True))
    assert "확인하지 못했어요" in course_answer(course, "영업시간 알려줘")


def test_조사를_받침에_맞춘다():
    course = _course(_place("성수식당", hours_unverified=True))
    assert "성수식당은" in course_answer(course, "영업시간 알려줘")


def test_정보가_전혀_없으면_없다고_한다():
    course = Course(id="c", items=[])
    assert "정보가 없어요" in course_answer(course, "영업시간 알려줘")


def test_다른_질문은_영향받지_않는다():
    course = _course(_place("성수커피", price=8000))
    assert "8,000원" in course_answer(course, "얼마야")
