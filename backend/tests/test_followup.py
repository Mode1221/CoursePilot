"""코스가 있을 때의 후속 요청 — 직전 조건을 이어받고 바뀐 부분만 반영한다."""
from datetime import time

from fastapi.testclient import TestClient

from app.pipeline.decomposition import parse_constraints
from app.pipeline.followup import followup_text

PREV = "토요일 성수 오후 2시 데이트 4시간"


def _c(text: str):
    return parse_constraints(followup_text(text, PREV, time(14, 0)))


def test_끝나는_시각은_끝_시각으로_읽는다():
    c = _c("7시에 끝나게 해줘")
    assert (c.region, c.start_time, c.end_time) == ("성수", time(14, 0), time(19, 0))


def test_상대_시간_이동():
    assert _c("1시간 늦게 시작하자").start_time == time(15, 0)
    assert _c("30분 일찍").start_time == time(13, 30)
    assert _c("두 시간 늦게").start_time == time(16, 0)


def test_새_시간대_날짜_소요시간이_옛_값을_대신한다():
    c = _c("내일 저녁으로 바꿔")
    assert c.start_time == time(18, 0) and c.region == "성수"
    assert _c("2시간만").duration_min == 120
    assert _c("점심으로").start_time == time(12, 0)


def test_이동_불만은_조건으로_바꾼다():
    assert _c("아 너무 멀다").max_travel_min == 10
    c = _c("걷기 싫어 차로 갈게")
    assert c.travel_mode.value == "car" and c.max_travel_min is None


def test_새_취향은_기존_조건에_더한다():
    c = _c("디저트 먹고 싶어")
    assert c.region == "성수" and "디저트" in c.keywords and c.start_time == time(14, 0)


def test_채팅으로_이어서_말하면_지역과_시간이_유지된다(monkeypatch):
    from app.config import settings
    from app.main import api
    from app.users import user_store

    monkeypatch.setattr(settings, "rate_limit_per_min", 10_000)
    c = TestClient(api)
    u = user_store.create("010-5555-6666")
    h = {"X-User-Id": u.id}
    cid = c.post("/courses", json={"owner_id": u.id}, headers=h).json()["id"]
    c.post(f"/courses/{cid}/generate", json={"text": "성수 오후 2시 데이트"}, headers=h)
    first = c.post(f"/courses/{cid}/generate", json={"text": "디저트 먹고 싶어"}, headers=h).json()
    assert first["course"]["region"] == "성수"
    later = c.post(f"/courses/{cid}/generate", json={"text": "1시간 늦게 시작하자"}, headers=h).json()
    items = later["course"]["items"]
    assert items and items[0]["arrive"].startswith("15:")
    msgs = c.get(f"/courses/{cid}/messages", headers=h).json()
    assert "지역을 못 알아들어" not in msgs[-1]["text"]


def test_다시_해줘는_다른_장소로(monkeypatch):
    from app.config import settings
    from app.main import api
    from app.users import user_store

    monkeypatch.setattr(settings, "rate_limit_per_min", 10_000)
    c = TestClient(api)
    u = user_store.create("010-5555-7777")
    h = {"X-User-Id": u.id}
    cid = c.post("/courses", json={"owner_id": u.id}, headers=h).json()["id"]
    a = c.post(f"/courses/{cid}/generate", json={"text": "성수 오후 2시 데이트"}, headers=h).json()
    b = c.post(f"/courses/{cid}/generate", json={"text": "다시 해줘"}, headers=h).json()
    ids = lambda r: [it["place"]["id"] for it in r["course"]["items"]]  # noqa: E731
    assert ids(b) and ids(a) != ids(b)


def test_다시_짠_코스는_바뀐_정도를_말한다():
    from app.main import _change_note

    assert _change_note(["a", "b"], ["a", "b"]) == "장소는 그대로예요."
    assert _change_note(["a", "b"], ["b", "a"]) == "장소는 그대로 두고 순서·시간만 맞췄어요."
    assert _change_note(["a", "b"], ["a", "c"]) == "1곳은 그대로 두고 1곳을 새로 골랐어요."
    assert _change_note(["a", "b"], ["c", "d"]) == "모두 새로 골랐어요."
    assert _change_note(["a", "b", "c"], ["a", "c"]) == "조건에 맞추느라 1곳을 뺐어요."


async def test_첫_자리를_바꿔도_시작_시각을_지킨다():
    from app.adapters.map_service import MockMapService
    from app.pipeline.edit import apply_edit, parse_edit
    from app.schemas import Course, Place, TimelineItem

    places = [Place(id=f"p{i}", name=f"p{i}", category="cafe", lat=37.5, lng=127.0) for i in range(2)]
    course = Course(id="c", region="성수", items=[
        TimelineItem(place=places[0], arrive=time(14), depart=time(15)),
        TimelineItem(place=places[1], arrive=time(15, 10), depart=time(16)),
    ])
    items = await apply_edit(course, parse_edit("첫번째 빼고 다 좋아"), MockMapService())
    assert items[0].place.id != "p0" and items[0].arrive == time(14)
    front = await apply_edit(course, parse_edit("맨 앞에 카페 넣어줘"), MockMapService())
    assert front[0].arrive == time(14)


def test_다시_해줘는_곳_수를_지킨다(monkeypatch):
    from app.config import settings
    from app.main import api
    from app.users import user_store

    monkeypatch.setattr(settings, "rate_limit_per_min", 10_000)
    c = TestClient(api)
    u = user_store.create("010-5555-8888")
    h = {"X-User-Id": u.id}
    cid = c.post("/courses", json={"owner_id": u.id}, headers=h).json()["id"]
    a = c.post(f"/courses/{cid}/generate", json={"text": "성수 오후 2시 데이트 4시간"}, headers=h).json()
    b = c.post(f"/courses/{cid}/generate", json={"text": "다시 해줘"}, headers=h).json()
    assert len(b["course"]["items"]) >= len(a["course"]["items"])
