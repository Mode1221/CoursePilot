from datetime import date, datetime, time

from fastapi.testclient import TestClient

from app.calendar import to_ics
from app.main import app
from app.schemas import Course, Place, Route, TimelineItem

client = TestClient(app)


def _item(name: str, arrive: time, depart: time, travel: int | None = None) -> TimelineItem:
    return TimelineItem(
        place=Place(id=name, name=name, lat=37.5, lng=127.0),
        arrive=arrive,
        depart=depart,
        travel_to_next=(
            Route(from_place_id=name, to_place_id="x", mode="walk", duration_min=travel,
                  distance_m=100)
            if travel
            else None
        ),
    )


def _course(items: list[TimelineItem]) -> Course:
    return Course(id="c1", title="t", items=items)


def test_장소마다_VEVENT를_만든다():
    ics = to_ics(
        _course([_item("A", time(13, 0), time(14, 0), 15), _item("B", time(14, 15), time(16, 0))]),
        day=date(2026, 1, 1),
        now=datetime(2026, 1, 1, 9),
    )
    assert ics.count("BEGIN:VEVENT") == 2
    assert "DTSTART:20260101T130000" in ics
    assert "DTEND:20260101T160000" in ics
    assert "다음 장소까지 15분" in ics


def test_자정을_넘기면_다음날로_넘어간다():
    ics = to_ics(
        _course([_item("A", time(22, 0), time(23, 30)), _item("B", time(0, 30), time(1, 30))]),
        day=date(2026, 1, 1),
        now=datetime(2026, 1, 1, 9),
    )
    assert "DTSTART:20260102T003000" in ics


def test_시각이_없는_장소는_건너뛴다():
    course = _course([TimelineItem(place=Place(id="p", name="p", lat=37.5, lng=127.0))])
    ics = to_ics(course, day=date(2026, 1, 1), now=datetime(2026, 1, 1, 9))
    assert "BEGIN:VEVENT" not in ics
    assert ics.startswith("BEGIN:VCALENDAR")


def test_특수문자를_이스케이프한다():
    course = _course([_item("카페; A, B", time(13, 0), time(14, 0))])
    ics = to_ics(course, day=date(2026, 1, 1), now=datetime(2026, 1, 1, 9))
    assert "SUMMARY:카페\; A\\, B" in ics


def test_엔드포인트가_ics를_내려준다():
    cid = client.post("/courses").json()["id"]
    res = client.get(f"/courses/{cid}/calendar.ics")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/calendar")
    assert "attachment" in res.headers["content-disposition"]
    assert res.text.startswith("BEGIN:VCALENDAR")


def test_없는_코스는_404():
    assert client.get("/courses/nope/calendar.ics").status_code == 404
