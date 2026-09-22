"""합의 코스 API — 토큰 권한·비공개·합치기·수락."""
import itertools

import pytest
from fastapi.testclient import TestClient

from app.main import api


@pytest.fixture
def client():
    return TestClient(api)


_phone_seq = itertools.count(7000)


def _signup(client) -> str:
    phone = f"010-0000-{next(_phone_seq):04d}"
    return client.post("/signup", json={"phone": phone}).json()["user_id"]


def _start(client):
    uid = _signup(client)
    h = {"X-User-Id": uid}
    cid = client.post("/courses", headers=h).json()["id"]
    st = client.post(
        f"/courses/{cid}/together", json={"text": "토요일 3시 성수", "owner_name": "민수", "partner_name": "지은"},
        headers=h,
    )
    assert st.status_code == 200, st.text
    token = client.get(f"/courses/{cid}/together/link", headers=h).json()["token"]
    return uid, h, cid, token


def test_시작은_생성자만(client):
    cid = client.post("/courses", headers={"X-User-Id": _signup(client)}).json()["id"]
    r = client.post(f"/courses/{cid}/together", json={"text": "성수"}, headers={"X-User-Id": "other"})
    assert r.status_code == 403


def test_상대는_토큰만으로_카드를_내고_상대의_답은_못_본다(client):
    uid, h, cid, token = _start(client)
    client.post(f"/courses/{cid}/together/input", json={"cravings": ["고기"], "budget_band": 50000}, headers=h)
    status = client.get(f"/together/{token}").json()
    assert status["submitted"] == ["민수"] and "cards" in status
    assert "inputs" not in status and "\"budget_band\":" not in client.get(f"/together/{token}").text
    r = client.post(f"/together/{token}/input", json={"condition": "tired", "cravings": ["디저트"], "dislikes": ["매운 거"]})
    assert r.status_code == 200 and sorted(r.json()["submitted"]) == ["민수", "지은"]


def test_잘못된_토큰은_404(client):
    assert client.get("/together/nope").status_code == 404
    assert client.post("/together/nope/input", json={}).status_code == 404


def test_카드_값_검증(client):
    _, _, _, token = _start(client)
    assert client.post(f"/together/{token}/input", json={"condition": "sleepy"}).status_code == 400
    assert client.post(f"/together/{token}/input", json={"cravings": ["초밥"]}).status_code == 400


def test_합쳐서_만든_코스에_반영_이유가_붙고_예산은_안_나간다(client):
    uid, h, cid, token = _start(client)
    client.post(f"/courses/{cid}/together/input", json={"cravings": ["고기"], "dislikes": ["웨이팅"], "budget_band": 50000}, headers=h)
    client.post(f"/together/{token}/input", json={"condition": "tired", "cravings": ["디저트"], "budget_band": 30000})
    r = client.post(f"/courses/{cid}/together/build", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    course = body["course"]
    assert course["items"], "코스가 비어 있다"
    whos = {a["who"] for it in course["items"] for a in it["attributions"]}
    whos |= {a["who"] for a in course["together"]["summary"]}  # 코스 전체 이유·못 찾은 취향은 요약 줄
    assert {"민수", "지은"} <= whos
    assert "inputs" not in course["together"] and "token" not in course["together"]
    assert "\"budget_band\":" not in r.text  # 카드 원문(예산 포함)은 어디에도 실리지 않는다
    # 공유 링크로 보는 코스에도 반영 칩은 있다
    shared = client.get(f"/courses/{cid}").json()
    assert shared["together"]["summary"] and "token" not in shared["together"] and "inputs" not in shared["together"]


def test_토큰으로는_AI_명령을_못_한다(client):
    _, _, cid, token = _start(client)
    r = client.post(f"/courses/{cid}/generate", json={"text": "다 지워"})
    assert r.status_code == 403


def test_둘_다_수락하면_확정(client):
    uid, h, cid, token = _start(client)
    client.post(f"/courses/{cid}/together/input", json={"cravings": ["고기"]}, headers=h)
    client.post(f"/together/{token}/input", json={"cravings": ["디저트"]})
    assert client.post(f"/together/{token}/accept").status_code == 400  # 아직 코스 없음
    client.post(f"/courses/{cid}/together/build", headers=h)
    assert client.post(f"/together/{token}/accept").json()["accepted_by"] == ["지은"]
    st = client.post(f"/courses/{cid}/together/accept", headers=h).json()
    assert sorted(st["accepted_by"]) == ["민수", "지은"]


def test_한_명만_냈어도_초안을_만든다(client):
    uid, h, cid, token = _start(client)
    client.post(f"/courses/{cid}/together/input", json={"cravings": ["고기"]}, headers=h)
    r = client.post(f"/courses/{cid}/together/build", headers=h)
    assert r.status_code == 200 and r.json()["course"]["items"]
