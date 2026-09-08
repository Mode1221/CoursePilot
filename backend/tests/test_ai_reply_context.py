from datetime import date, time

from app.main import _ai_reply
from app.schemas import Course, Place, TimelineItem

PLACE = Place(id="p1", name="카페 A", category="cafe", lat=37.5, lng=127.0)


def _course(**kwargs) -> Course:
    item = TimelineItem(place=PLACE, arrive=time(19, 0), depart=time(20, 0))
    return Course(id="c1", title="테스트", items=[item], **kwargs)


def test_reply_mentions_date_and_start_time():
    text = _ai_reply(_course(plan_date=date(2026, 9, 12)), False, False)
    assert "9월 12일" in text
    assert "19:00 시작" in text
    assert "1곳" in text


def test_reply_without_date_keeps_start_time():
    text = _ai_reply(_course(), False, False)
    assert "9월" not in text
    assert "19:00 시작" in text


def test_needs_confirmation_unchanged():
    assert "완화할까요" in _ai_reply(_course(), False, True)


def test_reply_mentions_start_place():
    from app.schemas import PlanConstraints

    text = _ai_reply(_course(), False, False, constraints=PlanConstraints(start_place="강남역"))
    assert "강남역 출발" in text


def test_reply_mentions_indoor_when_rainy():
    from app.schemas import PlanConstraints

    text = _ai_reply(_course(), False, False, constraints=PlanConstraints(prefer_indoor=True))
    assert "실내 위주" in text


def test_reply_unchanged_without_constraints():
    assert "출발" not in _ai_reply(_course(), False, False)


def test_reply_mentions_end_time():
    text = _ai_reply(_course(), False, False)
    assert "20:00쯤 마무리돼요" in text
