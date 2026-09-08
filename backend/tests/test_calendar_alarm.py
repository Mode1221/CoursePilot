from datetime import date, time

from app.calendar import ALARM_MINUTES_BEFORE, to_ics
from app.schemas import Course, Place, TimelineItem


def _place(pid: str) -> Place:
    return Place(id=pid, name=f"장소 {pid}", category="cafe", lat=37.5, lng=127.0)


def _course() -> Course:
    return Course(
        id="c1",
        title="성수동 데이트",
        items=[
            TimelineItem(place=_place("a"), arrive=time(13, 0), depart=time(14, 0)),
            TimelineItem(place=_place("b"), arrive=time(14, 30), depart=time(15, 30)),
        ],
    )


def test_alarm_only_on_first_event():
    ics = to_ics(_course(), day=date(2026, 9, 12))
    assert ics.count("BEGIN:VALARM") == 1
    assert f"TRIGGER:-PT{ALARM_MINUTES_BEFORE}M" in ics


def test_alarm_is_inside_first_event():
    ics = to_ics(_course(), day=date(2026, 9, 12))
    first_event = ics.split("BEGIN:VEVENT")[1]
    assert "BEGIN:VALARM" in first_event.split("END:VEVENT")[0]
