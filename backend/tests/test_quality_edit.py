"""성격만 말한 교체 요청("더 저렴한 곳으로")."""
from __future__ import annotations

import itertools

from fastapi.testclient import TestClient

from app.main import api
from app.pipeline.edit import parse_edit

client = TestClient(api)
_phones = itertools.count(1)


def test_순번이_있으면_그_자리를_바꾼다():
    cmd = parse_edit("2번째 좀 더 싼 데로")
    assert cmd.action == "replace"
    assert cmd.index == 1
    assert cmd.keyword == "저렴한"

    near = parse_edit("마지막 가까운 데로")
    assert near.action == "replace" and near.keyword == "가까운"


def test_대상이_없으면_되묻는다():
    assert parse_edit("더 저렴한 곳으로 바꿔").action == "clarify"
    assert parse_edit("분위기 좋은 곳으로 바꿔").action == "clarify"


def test_되물을_때는_코스도_크레딧도_그대로():
    uid = client.post(
        "/signup", json={"phone": f"010-4646-{next(_phones):04d}"}
    ).json()["user_id"]
    cid = client.post("/courses", headers={"X-User-Id": uid}).json()["id"]
    client.post(
        f"/courses/{cid}/generate",
        headers={"X-User-Id": uid},
        json={"text": "성수동 오전 10시 5시간 도보"},
    )
    items = client.get(f"/courses/{cid}").json()["items"]
    credits = client.get(f"/users/{uid}/credits", headers={"X-User-Id": uid}).json()[
        "questions_left"
    ]

    client.post(
        f"/courses/{cid}/generate",
        headers={"X-User-Id": uid},
        json={"text": "더 저렴한 곳으로 바꿔"},
    )

    assert "어느 자리를" in client.get(f"/courses/{cid}/messages").json()[-1]["text"]
    assert client.get(f"/courses/{cid}").json()["items"] == items
    assert (
        client.get(f"/users/{uid}/credits", headers={"X-User-Id": uid}).json()[
            "questions_left"
        ]
        == credits
    )


async def test_저렴한_데로_바꾸면_실제로_더_싼_곳이_온다():
    from app.adapters.map_service import MockMapService
    from app.pipeline.edit import apply_edit
    from app.schemas import Course, Place, TimelineItem

    def _place(pid: str, price: int) -> TimelineItem:
        return TimelineItem(
            place=Place(
                id=pid, name=pid, category="restaurant",
                lat=37.5, lng=127.0, price=price, rating=3.0,
            )
        )

    course = Course(id="c1", region="성수동", items=[_place("a", 50000), _place("b", 50000)])
    items = await apply_edit(course, parse_edit("2번째 좀 더 싼 데로"), MockMapService())
    assert items[1].place.price < 50000


async def test_평점_높은_곳으로_바꾸면_평점_기준으로_고른다():
    from app.adapters.map_service import MockMapService
    from app.pipeline.edit import apply_edit
    from app.schemas import Course, Place, TimelineItem

    course = Course(
        id="c2",
        region="성수동",
        items=[
            TimelineItem(
                place=Place(
                    id="a", name="a", category="restaurant",
                    lat=37.5, lng=127.0, rating=1.0,
                )
            ),
            TimelineItem(
                place=Place(
                    id="b", name="b", category="restaurant",
                    lat=37.5, lng=127.0, rating=1.0,
                )
            ),
        ],
    )
    items = await apply_edit(course, parse_edit("2번째 평점 높은 곳으로 바꿔"), MockMapService())
    assert (items[1].place.rating or 0) > 1.0
