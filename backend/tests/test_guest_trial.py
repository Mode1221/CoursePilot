"""체험(로그인 없이 1회) · 로그인 뒤 무료 몫 · 서비스 전체 상한 · 신원 위조 차단."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import usage
from app.config import settings
from app.main import api
from tests.helpers import member


@pytest.fixture
def client():
    return TestClient(api)


def _guest(client, nickname: str | None = None) -> str:
    res = client.post("/auth/guest", json={"agreed": True, "nickname": nickname})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["kind"] == "guest"
    return body["user_id"]


def H(uid: str) -> dict[str, str]:
    return {"X-User-Id": uid}


# ── 체험 시작 ─────────────────────────────────────────────────────────────
def test_동의_없이는_체험을_시작할_수_없다(client):
    assert client.post("/auth/guest", json={"agreed": False}).status_code == 400


def test_체험_계정은_게스트로_보인다(client):
    uid = _guest(client, "민수")
    me = client.get("/me", headers=H(uid)).json()
    assert me["kind"] == "guest"
    assert me["nickname"] == "민수"
    assert me["remaining"]["course"] == usage.LIMITS["course"].guest


def test_IP_당_하루_체험_발급_상한(client):
    for _ in range(settings.trial_guests_per_ip_day):
        _guest(client)
    res = client.post("/auth/guest", json={"agreed": True})
    assert res.status_code == 429


# ── 체험 몫 ───────────────────────────────────────────────────────────────
def test_체험은_코스_1개(client):
    uid = _guest(client)
    assert client.post("/courses", headers=H(uid)).status_code == 200
    res = client.post("/courses", headers=H(uid))
    assert res.status_code == 403
    assert res.json()["code"] == "login_required"


def test_같은_IP_의_다른_체험도_하루_코스_1개(client):
    a, b = _guest(client), _guest(client)
    assert client.post("/courses", headers=H(a)).status_code == 200
    res = client.post("/courses", headers=H(b))
    assert res.status_code == 403
    assert res.json()["code"] == "login_required"


def test_IP_코스_상한은_설정으로_늘린다(client, monkeypatch):
    monkeypatch.setattr(settings, "trial_courses_per_ip_day", 5)
    a, b = _guest(client), _guest(client)
    assert client.post("/courses", headers=H(a)).status_code == 200
    assert client.post("/courses", headers=H(b)).status_code == 200


def test_회원은_IP_상한과_무관하게_하루_몫(client, monkeypatch):
    monkeypatch.setitem(usage.LIMITS, "course", usage.Limit(guest=1, member=3))
    uid = member(client)
    for _ in range(3):
        assert client.post("/courses", headers=H(uid)).status_code == 200
    res = client.post("/courses", headers=H(uid))
    assert res.status_code == 429
    assert res.json()["code"] == "daily_limit"


def test_체험_AI_는_정해진_횟수까지(client, monkeypatch):
    monkeypatch.setitem(usage.LIMITS, "ai", usage.Limit(guest=2, member=30))
    uid = _guest(client)
    cid = client.post("/courses", headers=H(uid)).json()["id"]
    for _ in range(2):
        ok = client.post(f"/courses/{cid}/generate", json={"text": "성수동 오후 2시 3시간"}, headers=H(uid))
        assert ok.status_code == 200
    res = client.post(f"/courses/{cid}/generate", json={"text": "성수동 오후 2시 3시간"}, headers=H(uid))
    assert res.status_code == 403
    assert res.json()["code"] == "login_required"


def test_질문은_AI_몫을_쓰지_않는다(client, monkeypatch):
    monkeypatch.setitem(usage.LIMITS, "ai", usage.Limit(guest=2, member=30))
    uid = _guest(client)
    cid = client.post("/courses", headers=H(uid)).json()["id"]
    assert client.post(f"/courses/{cid}/generate", json={"text": "성수동 오후 2시 3시간"}, headers=H(uid)).status_code == 200
    for _ in range(3):  # 코스를 바꾸지 않는 질문은 몫을 돌려받는다
        res = client.post(f"/courses/{cid}/generate", json={"text": "여기 주차 되나요?"}, headers=H(uid))
        assert res.status_code == 200
    assert usage.remaining("ai", subject=uid, guest=True) == 1


def test_체험_합치기도_정해진_횟수까지(client, monkeypatch):
    monkeypatch.setitem(usage.LIMITS, "build", usage.Limit(guest=1, member=20))
    uid = _guest(client)
    cid = client.post("/courses", headers=H(uid)).json()["id"]
    client.post(f"/courses/{cid}/together", json={"text": "토요일 3시 성수"}, headers=H(uid))
    client.post(f"/courses/{cid}/together/input", json={"condition": "normal"}, headers=H(uid))
    assert client.post(f"/courses/{cid}/together/build", headers=H(uid)).status_code == 200
    res = client.post(f"/courses/{cid}/together/build", headers=H(uid))
    assert res.status_code == 403
    assert res.json()["code"] == "login_required"


def test_합칠_카드가_없으면_몫을_돌려준다(client, monkeypatch):
    monkeypatch.setitem(usage.LIMITS, "build", usage.Limit(guest=1, member=20))
    uid = _guest(client)
    cid = client.post("/courses", headers=H(uid)).json()["id"]
    client.post(f"/courses/{cid}/together", json={"text": "토요일 3시 성수"}, headers=H(uid))
    assert client.post(f"/courses/{cid}/together/build", headers=H(uid)).status_code == 400
    assert usage.remaining("build", subject=uid, guest=True) == 1


# ── 서비스 전체 상한 ──────────────────────────────────────────────────────
def test_서비스_전체_코스_상한에_닿으면_503(client, monkeypatch):
    monkeypatch.setitem(usage.GLOBAL_DAILY, "course", 1)
    a, b = member(client), member(client)
    assert client.post("/courses", headers=H(a)).status_code == 200
    res = client.post("/courses", headers=H(b))
    assert res.status_code == 503
    assert res.json()["code"] == "service_busy"
    # 서비스 몫에서 막히면 사람 몫은 돌려받는다
    assert usage.remaining("course", subject=b, guest=False) == usage.LIMITS["course"].member


def test_LLM_하루_상한을_넘으면_클라이언트가_없어진다(monkeypatch):
    from app import llm_client

    sentinel = object()
    monkeypatch.setattr(llm_client, "_anthropic_client", lambda: sentinel)
    monkeypatch.setitem(usage.GLOBAL_DAILY, "llm", 2)
    assert llm_client.get_anthropic_client() is sentinel
    assert llm_client.get_anthropic_client() is sentinel
    assert llm_client.get_anthropic_client() is None  # 규칙 기반 폴백


def test_Google_상세는_하루_상한도_본다(monkeypatch):
    from app.adapters import google
    from app.quota import quota_store

    quota_store.clear()
    monkeypatch.setitem(usage.GLOBAL_DAILY, "google.details", 1)
    assert google._consume("google.details") is True
    assert google._consume("google.details") is False
    quota_store.clear()


# ── 비싼 조회 ─────────────────────────────────────────────────────────────
def test_장소_검색은_신원이_없으면_IP_를_체험_몫으로_센다(client, monkeypatch):
    monkeypatch.setitem(usage.LIMITS, "search", usage.Limit(guest=2, member=300))
    for _ in range(2):
        assert client.get("/places/search", params={"region": "성수동"}).status_code == 200
    res = client.get("/places/search", params={"region": "성수동"})
    assert res.status_code == 403
    assert res.json()["code"] == "login_required"
    # 회원은 자기 몫
    assert client.get("/places/search", params={"region": "성수동"}, headers=H(member(client))).status_code == 200


def test_리뷰_요약_캐시는_질의를_바꿔도_장소_하나(client, monkeypatch):
    import app.main as main

    main._summary_cache.clear()
    monkeypatch.setitem(usage.LIMITS, "review", usage.Limit(guest=1, member=30))
    uid = member(client)
    body = {"place_id": "p-cache", "place_name": "테스트 카페"}
    first = client.post("/reviews/summary", json=body, headers=H(uid))
    assert first.status_code == 200
    if first.json()["count"]:
        # 캐시에 들어갔다면 질의 문구를 바꿔도 같은 결과(유료 호출 없음)
        again = client.post("/reviews/summary", json={**body, "query": "다른 문구"})
        assert again.status_code == 200
        assert again.json() == first.json()
    main._summary_cache.clear()


# ── 신원 위조 차단 ────────────────────────────────────────────────────────
def test_남의_id_를_적어도_그_사람_이름으로_AI_를_못_돌린다(client):
    """예전: 주인 없는 코스에서는 아무 X-User-Id 나 통과해 그 사람 크레딧·선호를 썼다."""
    from app.store import store

    victim = member(client)
    legacy = store.create(owner_id=None)  # 예전 비로그인 코스
    res = client.post(f"/courses/{legacy.id}/generate", json={"text": "성수동"}, headers=H(victim))
    assert res.status_code == 403
    assert client.patch(f"/courses/{legacy.id}", json={"title": "x"}, headers=H(victim)).status_code == 403


def test_서명이_틀리면_401(client, monkeypatch):
    monkeypatch.setattr(settings, "session_secret", "s" * 40)
    uid = _guest(client)
    res = client.post("/courses", headers={"X-User-Id": uid, "X-User-Token": "1.bad"})
    assert res.status_code == 401


def test_상대는_링크_토큰으로_손_편집을_할_수_있다(client):
    uid = member(client)
    cid = client.post("/courses", headers=H(uid)).json()["id"]
    st = client.post(f"/courses/{cid}/together", json={"text": "토요일 3시 성수"}, headers=H(uid))
    assert st.status_code == 200
    token = client.get(f"/courses/{cid}/together/link", headers=H(uid)).json()["token"]
    res = client.post(f"/courses/{cid}/items", json={"place_ids": []}, headers={"X-Together-Token": token})
    assert res.status_code == 200
    assert client.get(f"/courses/{cid}/messages", headers={"X-Together-Token": token}).status_code == 200
    wrong = client.post(f"/courses/{cid}/items", json={"place_ids": []}, headers={"X-Together-Token": "nope"})
    assert wrong.status_code == 403


# ── 독립 검토에서 나온 구멍 ───────────────────────────────────────────────
def test_질문만_반복해도_LLM_을_끝없이_쓰지_못한다(client, monkeypatch):
    """질문은 AI 몫을 돌려받지만 대신 '질문' 몫을 쓴다 — 다 쓰면 AI 몫을 쓴 것으로 남는다."""
    monkeypatch.setitem(usage.LIMITS, "ai", usage.Limit(guest=2, member=30))
    monkeypatch.setitem(usage.LIMITS, "ask", usage.Limit(guest=2, member=100))
    uid = _guest(client)
    cid = client.post("/courses", headers=H(uid)).json()["id"]
    assert client.post(f"/courses/{cid}/generate", json={"text": "성수동 오후 2시 3시간"}, headers=H(uid)).status_code == 200
    codes = [
        client.post(f"/courses/{cid}/generate", json={"text": "여기 주차 되나요?"}, headers=H(uid)).status_code
        for _ in range(6)
    ]
    # 질문 2번은 질문 몫, 3번째는 AI 몫 마지막 1회를 쓰고, 그다음부터는 막힌다
    assert codes[:3] == [200, 200, 200]
    assert codes[3:] == [403, 403, 403]


def test_리뷰_요약은_서버가_가진_이름만_쓴다(client, monkeypatch):
    """클라이언트가 보낸 이름으로 다른 가게 리뷰를 이 장소에 심지 못한다."""
    import app.main as main
    from app.places import place_repo
    from app.schemas import Place

    main._summary_cache.clear()
    seen: list[str] = []

    async def fake_fetch(name, limit=5):
        seen.append(name)
        return []

    monkeypatch.setattr("app.reviews.rag.fetch_filtered", fake_fetch)
    place_repo.upsert_many([Place(id="real-1", name="진짜 가게", lat=37.5, lng=127.0)])
    client.post("/reviews/summary", json={"place_id": "real-1", "place_name": "다른 가게"}, headers=H(member(client)))
    assert seen == ["진짜 가게"]
    # 모르는 장소는 유료 호출도, 횟수 차감도 없다
    before = usage.counters.used(f"d:{usage.today()}:review:x")
    res = client.post("/reviews/summary", json={"place_id": "nope", "place_name": "아무 가게"})
    assert res.json()["count"] == 0 and seen == ["진짜 가게"]
    assert usage.counters.used(f"d:{usage.today()}:review:x") == before


def test_신원_없는_IP_몫은_하루_단위다(client, monkeypatch):
    monkeypatch.setitem(usage.LIMITS, "search", usage.Limit(guest=1, member=300))
    assert client.get("/places/search", params={"region": "성수동"}).status_code == 200
    keys = [k for k in usage.counters._mem if ":search:ip-" in k]
    assert keys and all(k.startswith(f"d:{usage.today()}:") for k in keys)


def test_비ASCII_링크_토큰은_예외가_아니라_불일치():
    """헤더에 비 ASCII 가 오면 str 상수 시간 비교가 TypeError(500)를 냈다."""
    from app.identity import token_matches

    assert token_matches("tok-1", "토큰") is False
    assert token_matches("tok-1", "tok-1") is True
    assert token_matches("tok-1", None) is False


async def test_대화는_편집_권한자만_소켓으로_받는다(monkeypatch):
    from app import realtime
    from app.schemas import Course, TogetherState
    from app.store import store

    entered: list[str] = []

    async def _enter(sid, room):
        entered.append(room)

    async def _emit(*a, **k):
        return None

    monkeypatch.setattr(realtime.sio, "enter_room", _enter)
    monkeypatch.setattr(realtime.sio, "emit", _emit)
    store.save(Course(id="cc1", owner_id="owner-x", together=TogetherState(token="tok-1", request_text="성수")))
    await realtime.join("viewer", {"course_id": "cc1"})
    assert entered == ["cc1"]  # 공유 링크로 보는 사람: 코스 상태만
    entered.clear()
    await realtime.join("partner", {"course_id": "cc1", "together_token": "tok-1"})
    assert entered == ["cc1", "cc1#chat"]
