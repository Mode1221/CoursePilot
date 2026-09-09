"""코스 장소 선택 근거."""
from __future__ import annotations

import itertools
from datetime import time

from fastapi.testclient import TestClient

from app.main import api
from app.reasons import course_reasons
from app.schemas import Course, Place, Route, TimelineItem, TravelMode

client = TestClient(api)
_phones = itertools.count(1)


def _course() -> Course:
    a = TimelineItem(
        place=Place(
            id="a", name="조용한 한식당", category="음식점>한식",
            lat=37.5, lng=127.0, rating=4.6, price=20000,
        ),
        arrive=time(18, 0),
        depart=time(19, 30),
        travel_to_next=Route(
            from_place_id="a", to_place_id="b",
            mode=TravelMode.WALK, duration_min=7, distance_m=500,
        ),
    )
    b = TimelineItem(
        place=Place(id="b", name="디저트 카페", category="카페", lat=37.51, lng=127.01, rating=4.0),
        arrive=time(19, 37),
        depart=time(20, 37),
    )
    return Course(id="c1", region="성수동", items=[a, b])


def test_키워드_평점_예산_근거를_모은다():
    reasons = course_reasons(_course(), "성수동 조용한 곳 3만원 이하 저녁 6시")
    assert any("조용한" in r for r in reasons["a"])
    assert any("평점 4.6" in r for r in reasons["a"])
    assert any("예산 안" in r for r in reasons["a"])


def test_이어지는_장소는_이동시간을_근거로_쓴다():
    reasons = course_reasons(_course(), "성수동 저녁")
    assert any("7분" in r for r in reasons["b"])


def test_근거가_없으면_빈_목록():
    course = _course()
    course.items[1].place.rating = None
    reasons = course_reasons(course, "")
    assert reasons["b"] == [] or all(isinstance(r, str) for r in reasons["b"])


def test_엔드포인트가_코스별_근거를_돌려준다():
    uid = client.post(
        "/signup", json={"phone": f"010-6363-{next(_phones):04d}"}
    ).json()["user_id"]
    cid = client.post("/courses", headers={"X-User-Id": uid}).json()["id"]
    client.post(
        f"/courses/{cid}/generate",
        headers={"X-User-Id": uid},
        json={"text": "성수동 오전 10시 5시간 도보"},
    )
    body = client.get(f"/courses/{cid}/reasons").json()
    items = client.get(f"/courses/{cid}").json()["items"]
    assert set(body["reasons"]) == {it["place"]["id"] for it in items}


def test_없는_코스는_404():
    assert client.get("/courses/nope/reasons").status_code == 404
