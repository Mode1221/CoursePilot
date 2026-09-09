"""전체 초기화 표현 — 새 코스를 만들지 않고 비운다."""
from __future__ import annotations

import itertools

from fastapi.testclient import TestClient

from app.adapters.map_service import MockMapService
from app.main import api
from app.pipeline.edit import apply_edit, parse_edit
from app.schemas import Course, Place, TimelineItem

client = TestClient(api)
_phones = itertools.count(1)


def test_전체_삭제_표현을_인식한다():
    for text in ("다 지워", "전부 삭제해줘", "초기화", "싹 비워줘"):
        assert parse_edit(text).action == "clear", text
    # 순번을 지목한 삭제는 그대로 remove
    assert parse_edit("1번째 지워").action == "remove"


async def test_적용하면_코스가_빈다():
    course = Course(
        id="c1",
        items=[TimelineItem(place=Place(id="a", name="가", lat=37.5, lng=127.0))],
    )
    assert await apply_edit(course, parse_edit("다 지워"), MockMapService()) == []


def test_비운_뒤_안내문이_나온다():
    uid = client.post("/signup", json={"phone": f"010-8888-{next(_phones):04d}"}).json()["user_id"]
    cid = client.post("/courses", headers={"X-User-Id": uid}).json()["id"]
    client.post(
        f"/courses/{cid}/generate",
        headers={"X-User-Id": uid},
        json={"text": "성수동 오전 10시 5시간 도보"},
    )
    client.post(
        f"/courses/{cid}/generate", headers={"X-User-Id": uid}, json={"text": "다 지워"}
    )
    assert client.get(f"/courses/{cid}").json()["items"] == []
    assert "비웠어요" in client.get(f"/courses/{cid}/messages").json()[-1]["text"]
