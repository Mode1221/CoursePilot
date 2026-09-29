"""이동 질문에는 구간별 수단·시간으로 답한다."""
from datetime import time

import pytest

from app.answers import course_answer
from app.schemas import Course, Place, Route, TimelineItem, TravelMode


def _course(mode=TravelMode.WALK, with_route=True) -> Course:
    p1 = Place(id="p1", name="성수커피", lat=37.5, lng=127.0)
    p2 = Place(id="p2", name="성수식당", lat=37.51, lng=127.01)
    route = (
        Route(from_place_id="p1", to_place_id="p2", mode=mode, duration_min=12, distance_m=800)
        if with_route
        else None
    )
    return Course(
        id="c",
        items=[
            TimelineItem(place=p1, arrive=time(13, 0), depart=time(14, 0), travel_to_next=route),
            TimelineItem(place=p2, arrive=time(14, 12), depart=time(15, 30)),
        ],
    )


@pytest.mark.parametrize("question", ["이동 시간 얼마나 돼", "어떻게 가?", "걸어서 갈 만해?"])
def test_구간별_이동을_답한다(question):
    answer = course_answer(_course(), question)
    assert "도보 12분" in answer and "모두 12분" in answer


def test_수단_이름을_사람_말로_바꾼다():
    assert "대중교통" in course_answer(_course(TravelMode.TRANSIT), "어떻게 가")


def test_경로가_없으면_없다고_한다():
    assert "이동 정보가 아직 없어요" in course_answer(_course(with_route=False), "어떻게 가")


def test_비용_질문과_섞이지_않는다():
    # "이동 시간 얼마나"의 '얼마'가 비용 답변으로 새면 안 된다
    assert "원" not in course_answer(_course(), "이동 시간 얼마나 돼")
