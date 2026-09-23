"""칸별 대안 — 생성 시 부착, 교체하면 원래 장소가 대안으로 돌아간다."""
import itertools

import pytest
from fastapi.testclient import TestClient

from app.main import api
from app.pipeline.planner import attach_alternatives
from app.schemas import Place, PlanConstraints, TimelineItem

_seq = itertools.count(8300)


def _p(pid, name, cat, lat=37.5445, lng=127.0557):
    return Place(id=pid, name=name, category=cat, lat=lat, lng=lng)


def test_같은_성격_가까운_곳을_대안으로_이름_중복_없이():
    tl = [TimelineItem(place=_p("m1", "갈비집", "음식점 > 한식 > 육류,고기")),
          TimelineItem(place=_p("c1", "카페A", "음식점 > 카페"))]
    pool = [_p("m2", "삼겹집", "음식점 > 한식 > 육류,고기"), _p("m3", "먼고깃집", "음식점 > 한식 > 육류,고기", lat=37.60),
            _p("c2", "카페B", "음식점 > 카페"), _p("c3", "카페B", "음식점 > 카페"), _p("m1", "갈비집", "음식점 > 고기")]
    attach_alternatives(tl, pool, PlanConstraints())
    meal, cafe = tl
    assert [a.id for a in meal.alternatives][0] == "m2"  # 가까운 곳 먼저, 코스에 이미 있는 곳 제외
    assert "m1" not in [a.id for a in meal.alternatives]
    assert [a.name for a in cafe.alternatives] == ["카페B"]  # 같은 이름은 하나만


def test_합의_코스면_칸_주인_취향에_맞는_대안이_앞():
    tl = [TimelineItem(place=_p("m1", "한식당", "음식점 > 한식"))]
    pool = [_p("m2", "백반집", "음식점 > 한식"), _p("m3", "파스타집", "음식점 > 양식 > 이탈리안")]
    attach_alternatives(tl, pool, PlanConstraints(slot_focus=[["meal", "양식"]]))
    assert tl[0].alternatives[0].id == "m3"


@pytest.fixture
def client():
    return TestClient(api)


def test_생성된_코스엔_대안이_있고_교체하면_원래_장소가_대안으로(client):
    uid = client.post("/signup", json={"phone": f"010-0000-{next(_seq):04d}"}).json()["user_id"]
    h = {"X-User-Id": uid}
    cid = client.post("/courses", headers=h).json()["id"]
    course = client.post(f"/courses/{cid}/generate", json={"text": "성수동 오후 2시 3시간 코스"}, headers=h).json()["course"]
    first = course["items"][0]
    assert first["alternatives"], "대안이 비어 있다"
    alt = first["alternatives"][0]
    ids = [alt["id"], *[it["place"]["id"] for it in course["items"][1:]]]
    swapped = client.post(f"/courses/{cid}/items", json={"place_ids": ids}).json()
    new_first = swapped["items"][0]
    assert new_first["place"]["id"] == alt["id"]
    assert first["place"]["id"] in [a["id"] for a in new_first["alternatives"]]  # 되돌아갈 수 있다
