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


def test_알람은_이벤트_속성_뒤에_온다():
    """VALARM 은 VEVENT 의 하위 컴포넌트 — 속성 사이에 끼면 파싱이 깨지는 앱이 있다."""
    from app.calendar import to_ics
    from app.schemas import Route, TravelMode

    course = Course(
        id="c1",
        title="성수동 코스",
        plan_date=date(2026, 9, 12),
        items=[
            TimelineItem(
                place=Place(id="a", name="가", address="성수동 1", lat=37.5, lng=127.0),
                arrive=time(18, 0),
                depart=time(19, 0),
                travel_to_next=Route(
                    from_place_id="a", to_place_id="b",
                    mode=TravelMode.WALK, duration_min=10, distance_m=700,
                ),
            ),
            TimelineItem(
                place=Place(id="b", name="나", address="성수동 2", lat=37.51, lng=127.01),
                arrive=time(19, 10),
                depart=time(20, 10),
            ),
        ],
    )
    lines = to_ics(course).split("\r\n")
    begin = lines.index("BEGIN:VALARM")
    end = lines.index("END:VALARM")
    assert lines[end + 1] == "END:VEVENT"
    # 알람 앞에는 이벤트 속성들이 모두 나와 있어야 한다
    before = lines[:begin]
    assert any(line.startswith("GEO:") for line in before)
    assert any(line.startswith("LOCATION:") for line in before)
    assert any(line.startswith("DESCRIPTION:다음 장소까지") for line in before)
