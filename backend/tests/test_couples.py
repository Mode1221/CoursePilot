"""우리 기록 — 다녀온 곳 제외·각자 평가·양보 장부."""
import itertools

import pytest
from fastapi.testclient import TestClient

from app.couples import CoupleState, couple_store
from app.funnel import funnel_store
from app.main import api


def test_다녀온_곳은_빼되_둘_다_좋았던_곳은_남기고_누구라도_싫었던_곳은_뺀다():
    st = CoupleState(visited=["a", "b", "c"], ratings={"민수": {"a": 1, "d": -1}, "지은": {"a": 1, "b": 1}})
    assert st.exclude_ids() == {"b", "c", "d"}  # a 는 둘 다 👍 → 또 가자


_seq = itertools.count(8500)


@pytest.fixture
def client():
    couple_store.reset()
    funnel_store.reset()
    return TestClient(api)


def _together(client):
    uid = client.post("/signup", json={"phone": f"010-0000-{next(_seq):04d}"}).json()["user_id"]
    h = {"X-User-Id": uid}
    cid = client.post("/courses", headers=h).json()["id"]
    client.post(f"/courses/{cid}/together", json={"text": "성수 오후 2시", "owner_name": "민수", "partner_name": "지은"}, headers=h)
    tok = client.get(f"/courses/{cid}/together/link", headers=h).json()["token"]
    client.post(f"/courses/{cid}/together/input", json={"cravings": ["고기"]}, headers=h)
    client.post(f"/together/{tok}/input", json={"cravings": ["디저트"]})
    course = client.post(f"/courses/{cid}/together/build", headers=h).json()["course"]
    return uid, h, cid, tok, course


def test_다녀온_뒤_같은_커플의_다음_코스는_그곳을_빼고_안내한다(client):
    uid, h, cid, tok, course = _together(client)
    visited = {it["place"]["id"] for it in course["items"]}
    assert client.post(f"/courses/{cid}/complete").status_code == 200
    # 같은 커플(같은 시작자 + 같은 상대 이름)의 새 코스
    cid2 = client.post("/courses", headers=h).json()["id"]
    client.post(f"/courses/{cid2}/together", json={"text": "성수 오후 2시", "owner_name": "민수", "partner_name": "지은"}, headers=h)
    tok2 = client.get(f"/courses/{cid2}/together/link", headers=h).json()["token"]
    client.post(f"/courses/{cid2}/together/input", json={"cravings": ["고기"]}, headers=h)
    client.post(f"/together/{tok2}/input", json={"cravings": ["디저트"]})
    course2 = client.post(f"/courses/{cid2}/together/build", headers=h).json()["course"]
    again = {it["place"]["id"] for it in course2["items"]}
    assert not (again & visited) or len(again & visited) < len(visited)
    assert course2["together"]["memory_note"] and "빼고" in course2["together"]["memory_note"]


def test_각자_몰래_평가하고_남의_평가는_안_보인다(client):
    uid, h, cid, tok, course = _together(client)
    pid = course["items"][0]["place"]["id"]
    mine = client.post(f"/courses/{cid}/together/rate", json={"ratings": {pid: 1, "남의장소": 1}}, headers=h).json()
    assert mine == {"mine": {pid: 1}}  # 코스에 없는 장소는 무시
    theirs = client.post(f"/together/{tok}/rate", json={"ratings": {pid: -1}}).json()
    assert theirs == {"mine": {pid: -1}}  # 상대 응답엔 시작한 사람 평가가 없다
