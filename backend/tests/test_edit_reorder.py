"""순서 재배치 편집 명령."""
from __future__ import annotations

from app.adapters.map_service import MockMapService
from app.pipeline.edit import apply_edit, parse_edit
from app.schemas import Course, Place, TimelineItem


def _course() -> Course:
    # 일부러 멀리→가까이→멀리 순으로 꼬아 둔다
    places = [
        Place(id="a", name="가", lat=37.500, lng=127.000),
        Place(id="b", name="나", lat=37.560, lng=127.060),
        Place(id="c", name="다", lat=37.505, lng=127.005),
    ]
    return Course(id="c1", region="성수동", items=[TimelineItem(place=p) for p in places])


async def test_순서를_다시_짜면_가까운_순으로_이어진다():
    course = _course()
    items = await apply_edit(course, parse_edit("순서 바꿔줘"), MockMapService())
    assert [it.place.id for it in items] == ["a", "c", "b"]


async def test_두곳_이하면_그대로_둔다():
    course = _course()
    course.items = course.items[:2]
    items = await apply_edit(course, parse_edit("동선 정리해줘"), MockMapService())
    assert [it.place.id for it in items] == ["a", "b"]


def test_이미_최적이면_찾지_못했다고_하지_않는다():
    import itertools

    from fastapi.testclient import TestClient

    from app.main import api

    client = TestClient(api)
    phones = itertools.count(1)
    uid = client.post(
        "/signup", json={"phone": f"010-7777-{next(phones):04d}"}
    ).json()["user_id"]
    cid = client.post("/courses", headers={"X-User-Id": uid}).json()["id"]
    client.post(
        f"/courses/{cid}/generate",
        headers={"X-User-Id": uid},
        json={"text": "성수동 오전 10시 5시간 도보"},
    )
    client.post(
        f"/courses/{cid}/generate",
        headers={"X-User-Id": uid},
        json={"text": "순서 바꿔줘"},
    )
    text = client.get(f"/courses/{cid}/messages").json()[-1]["text"]
    assert "찾지 못했어요" not in text


async def test_두_자리를_지목하면_그_둘만_맞바꾼다():
    cmd = parse_edit("첫번째랑 두번째 순서 바꿔")
    assert cmd.action == "swap"
    items = await apply_edit(_course(), cmd, MockMapService())
    assert [it.place.id for it in items] == ["b", "a", "c"]


async def test_마지막_지목_스왑도_동작한다():
    items = await apply_edit(_course(), parse_edit("마지막이랑 1번 순서 바꿔"), MockMapService())
    assert [it.place.id for it in items] == ["c", "b", "a"]


async def test_없는_순번_스왑은_그대로_둔다():
    course = _course()
    items = await apply_edit(course, parse_edit("8번이랑 9번 순서 바꿔"), MockMapService())
    assert [it.place.id for it in items] == ["a", "b", "c"]


def test_순서_변경_안내는_바뀐_순서를_알려준다():
    import itertools

    from fastapi.testclient import TestClient

    from app.main import api

    client = TestClient(api)
    phones = itertools.count(1)
    uid = client.post(
        "/signup", json={"phone": f"010-1919-{next(phones):04d}"}
    ).json()["user_id"]
    cid = client.post("/courses", headers={"X-User-Id": uid}).json()["id"]
    client.post(
        f"/courses/{cid}/generate",
        headers={"X-User-Id": uid},
        json={"text": "성수동 오전 10시 5시간 도보"},
    )
    client.post(
        f"/courses/{cid}/generate",
        headers={"X-User-Id": uid},
        json={"text": "첫번째랑 두번째 순서 바꿔"},
    )
    text = client.get(f"/courses/{cid}/messages").json()[-1]["text"]
    assert "순서를 바꿨어요" in text
    assert "총 이동" in text
