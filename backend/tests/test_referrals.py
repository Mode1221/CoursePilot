"""유입 경로(첫 방문 출처)와 초대 보상 — 새 회원만·1번·초대자 상한·서명 신원·QA 제외·체험→회원."""
from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app import usage
from app.config import settings
from app.main import api
from app.referrals import (
    INVITE_REWARD_CAP,
    SOURCE_INVITE,
    clean_source,
    referral_store,
)
from tests.helpers import member

QA = "q" * 40
CB = "https://coursepilot.example/auth/kakao"
_seq = itertools.count(1)
BASE = usage.LIMITS["course"].member
BONUS = usage.INVITE_BONUS["course"]


@pytest.fixture
def client(monkeypatch):
    from app.adapters import kakao_auth

    monkeypatch.setattr(settings, "kakao_login_client_id", "login-app-key")
    monkeypatch.setattr(settings, "cors_origins", ["https://coursepilot.example"])
    monkeypatch.setattr(settings, "qa_token", QA)

    async def fake(code: str, redirect_uri: str, client=None) -> str:
        return code  # 테스트에서는 인가 코드가 곧 카카오 회원번호

    monkeypatch.setattr(kakao_auth, "kakao_user_id", fake)
    return TestClient(api)


def H(uid: str, token: str | None = None) -> dict[str, str]:
    h = {"X-User-Id": uid}
    if token:
        h["X-User-Token"] = token
    return h


def _phone() -> str:
    return f"0106{next(_seq):07d}"


def _invite(client, owner: str, token: str | None = None) -> tuple[str, str]:
    """owner 의 같이 정하기 링크. (코스 id, 링크 토큰)"""
    cid = client.post("/courses", headers=H(owner, token)).json()["id"]
    res = client.post(f"/courses/{cid}/together", json={"text": "토요일 3시 성수"}, headers=H(owner, token))
    assert res.status_code == 200, res.text
    link = client.get(f"/courses/{cid}/together/link", headers=H(owner, token)).json()["token"]
    return cid, link


def _kakao(client, kid: str, headers: dict | None = None, **arrival) -> dict:
    res = client.post("/auth/kakao", json={"code": kid, "redirect_uri": CB, **arrival}, headers=headers or {})
    assert res.status_code == 200, res.text
    return res.json()


def _course_limit(client, uid: str) -> int:
    return client.get("/me", headers=H(uid)).json()["limits"]["course"]


def _kid() -> str:
    return f"k{next(_seq)}"


# ── 출처 정리 ─────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Instagram", "instagram"),
        ("  Kakao Talk! ", "kakaotalk"),
        ("threads_ad-01", "threads_ad-01"),
        ("인스타", None),
        ("!!!", None),
        ("", None),
        (None, None),
        ("a" * 50, "a" * 32),
        ("<script>x</script>", "scriptxscript"),
    ],
)
def test_출처는_소문자_영숫자_32자로_정리한다(raw, expected):
    assert clean_source(raw) == expected


def test_체험을_시작하면_첫_방문_출처를_남긴다(client):
    uid = client.post(
        "/auth/guest", json={"agreed": True, "source": "Insta_Ad!", "campaign": "Fall 2026"}
    ).json()["user_id"]
    acq = referral_store.get(uid)
    assert acq.source == "insta_ad" and acq.campaign == "fall2026"
    assert acq.guest_at is not None and acq.member_at is None


def test_출처가_없는_가입도_기록은_남는다(client):
    res = client.post("/signup", json={"phone": _phone()}).json()
    acq = referral_store.get(res["user_id"])
    assert acq.source is None and acq.member_at is not None
    assert res["invite_reward"] is None


def test_첫_방문_출처는_가입_때_덮어쓰지_않는다(client):
    guest = client.post("/auth/guest", json={"agreed": True, "source": "threads"}).json()["user_id"]
    res = _kakao(client, _kid(), headers=H(guest), source="naver")
    acq = referral_store.get(res["user_id"])
    assert acq.source == "threads"  # 처음 온 곳
    assert acq.member_at is not None
    assert referral_store.get(guest) is None  # 체험 기록은 회원 쪽으로 옮겨졌다


def test_너무_긴_출처는_거절한다(client):
    assert client.post("/auth/guest", json={"agreed": True, "source": "x" * 65}).status_code == 422


# ── 초대 보상 ─────────────────────────────────────────────────────────────
def test_링크로_온_새_회원과_초대자_모두_보상(client):
    owner = member(client)
    cid, link = _invite(client, owner)
    assert _course_limit(client, owner) == BASE

    res = client.post("/signup", json={"phone": _phone(), "invite": link}).json()
    assert res["invite_reward"] == {"days": usage.INVITE_BONUS_DAYS, "extra": usage.INVITE_BONUS}
    new = res["user_id"]
    assert _course_limit(client, new) == BASE + BONUS
    assert _course_limit(client, owner) == BASE + BONUS
    me = client.get("/me", headers=H(new)).json()
    assert me["invite_bonus"]["extra"]["course"] == BONUS
    assert me["remaining"]["course"] == BASE + BONUS

    acq = referral_store.get(new)
    assert acq.source == SOURCE_INVITE and acq.inviter_id == owner and acq.course_id == cid


def test_카카오_가입도_보상하고_명시한_출처는_지킨다(client):
    owner = member(client)
    _, link = _invite(client, owner)
    res = _kakao(client, _kid(), invite=link, source="kakao_share")
    assert res["invite_reward"] is not None
    assert referral_store.get(res["user_id"]).source == "kakao_share"


def test_이미_있던_회원이_로그인하면_보상이_없다(client):
    owner = member(client)
    _, link = _invite(client, owner)
    kid = _kid()
    first = _kakao(client, kid)  # 링크 없이 먼저 가입해 둔 사람
    again = _kakao(client, kid, invite=link)
    assert again["user_id"] == first["user_id"]
    assert again["invite_reward"] is None
    assert _course_limit(client, owner) == BASE


def test_같은_로그인_수단으로는_한_번만_받는다(client):
    """탈퇴하고 같은 카카오로 다시 가입해도 두 번째 보상은 없다."""
    owner = member(client)
    _, link = _invite(client, owner)
    kid = _kid()
    first = _kakao(client, kid, invite=link)
    assert first["invite_reward"] is not None
    assert client.delete(f"/users/{first['user_id']}", headers=H(first["user_id"])).status_code == 200
    again = _kakao(client, kid, invite=link)
    assert again["user_id"] != first["user_id"]  # 새 계정이긴 하다
    assert again["invite_reward"] is None
    assert _course_limit(client, again["user_id"]) == BASE


def test_초대자_한_사람당_30일_상한(client):
    owner = member(client)
    _, link = _invite(client, owner)
    for _ in range(INVITE_REWARD_CAP):
        assert _kakao(client, _kid(), invite=link)["invite_reward"] is not None
    over = _kakao(client, _kid(), invite=link)
    assert over["invite_reward"] is None
    assert _course_limit(client, over["user_id"]) == BASE
    # 초대로 온 가입으로는 계속 센다(보상만 멈춘다)
    assert referral_store.get(over["user_id"]).inviter_id == owner
    assert client.get("/admin/growth").json()["windows"]["30d"]["rewards_granted"] == INVITE_REWARD_CAP


def test_초대자는_클라이언트가_적은_id_가_아니라_링크_주인(client):
    owner = member(client)
    bystander = member(client)
    _, link = _invite(client, owner)
    # 예전 referrer_id 나 임의 필드로 남을 초대자로 적어도 무시된다
    res = client.post(
        "/signup", json={"phone": _phone(), "invite": link, "referrer_id": bystander, "inviter_id": bystander}
    ).json()
    assert res["invite_reward"] is not None
    assert _course_limit(client, owner) == BASE + BONUS
    assert _course_limit(client, bystander) == BASE
    # 초대자 id 만 적어서는(링크 토큰 없이) 아무 일도 없다
    solo = client.post("/signup", json={"phone": _phone(), "referrer_id": owner}).json()
    assert solo["invite_reward"] is None


def test_없는_링크_토큰은_보상이_없다(client):
    res = client.post("/signup", json={"phone": _phone(), "invite": "nope"}).json()
    assert res["invite_reward"] is None
    assert referral_store.get(res["user_id"]).source is None


def test_서명이_있는_환경에서도_초대자는_서명된_코스_주인(client, monkeypatch):
    monkeypatch.setattr(settings, "session_secret", "s" * 40)
    owner = client.post("/signup", json={"phone": _phone()}).json()
    _, link = _invite(client, owner["user_id"], owner["token"])
    res = client.post("/signup", json={"phone": _phone(), "invite": link}).json()
    assert res["invite_reward"] is not None
    assert referral_store.get(res["user_id"]).inviter_id == owner["user_id"]


def test_자기_링크로_자기_체험을_가입시키면_보상이_없다(client):
    """체험으로 링크를 만든 사람이 그 체험 계정을 들고 가입하는 건 초대가 아니다."""
    guest = client.post("/auth/guest", json={"agreed": True}).json()["user_id"]
    _, link = _invite(client, guest)
    res = _kakao(client, _kid(), headers=H(guest), invite=link)
    assert res["moved_courses"] == 1
    assert res["invite_reward"] is None


def test_QA_요청은_보상도_출처도_남기지_않는다(client):
    owner = member(client)
    _, link = _invite(client, owner)
    qa = {"X-QA-Token": QA}
    guest = client.post("/auth/guest", json={"agreed": True, "source": "qa"}, headers=qa).json()["user_id"]
    assert referral_store.get(guest) is None
    res = client.post("/signup", json={"phone": _phone(), "invite": link, "source": "qa"}, headers=qa).json()
    assert res["invite_reward"] is None
    assert referral_store.get(res["user_id"]) is None
    assert _course_limit(client, owner) == BASE
    w = client.get("/admin/growth").json()["windows"]["7d"]
    assert "qa" not in w["signups_by_source"] and "qa" not in w["guests_by_source"]


def test_QA_전용_회원을_초대자로_한_보상은_없다(client):
    qa = client.post("/admin/qa-session", headers={"X-QA-Token": QA}).json()["user_id"]
    _, link = _invite(client, qa)  # QA 헤더 없이 만든 링크라도
    assert client.post("/signup", json={"phone": _phone(), "invite": link}).json()["invite_reward"] is None


def test_링크로_체험을_시작했다가_가입해도_보상(client):
    """상대가 링크 → 체험 시작(토큰 기억) → 나중에 카카오 가입. 가입 요청에 토큰이 없어도 체험 기록으로 잇는다."""
    owner = member(client)
    cid, link = _invite(client, owner)
    guest = client.post("/auth/guest", json={"agreed": True, "invite": link}).json()["user_id"]
    acq = referral_store.get(guest)
    assert acq.source == SOURCE_INVITE and acq.inviter_id == owner and acq.course_id == cid

    res = _kakao(client, _kid(), headers=H(guest))
    assert res["invite_reward"] is not None
    new = res["user_id"]
    assert _course_limit(client, new) == BASE + BONUS
    assert _course_limit(client, owner) == BASE + BONUS
    moved = referral_store.get(new)
    assert moved.source == SOURCE_INVITE and moved.guest_at is not None and moved.member_at is not None


def test_링크로_체험한_사람이_기존_계정으로_로그인하면_보상이_없다(client):
    """체험 기록에 초대가 있어도 이미 있던 회원 계정으로 들어가면 새 회원이 아니다."""
    owner = member(client)
    _, link = _invite(client, owner)
    kid = _kid()
    _kakao(client, kid)  # 예전에 가입해 둔 계정
    guest = client.post("/auth/guest", json={"agreed": True, "invite": link}).json()["user_id"]
    res = _kakao(client, kid, headers=H(guest), invite=link)
    assert res["invite_reward"] is None
    assert _course_limit(client, owner) == BASE
    assert _course_limit(client, res["user_id"]) == BASE


def test_체험으로_초대한_사람은_가입하면_보상을_이어받는다(client):
    inviter_guest = client.post("/auth/guest", json={"agreed": True}).json()["user_id"]
    _, link = _invite(client, inviter_guest)
    assert client.post("/signup", json={"phone": _phone(), "invite": link}).json()["invite_reward"] is not None
    # 체험 몫에는 보상을 더하지 않는다(체험은 평생 1회분)
    assert _course_limit(client, inviter_guest) == usage.LIMITS["course"].guest
    res = _kakao(client, _kid(), headers=H(inviter_guest))
    assert res["invite_reward"] is None  # 초대자 본인의 가입은 초대가 아니다
    assert _course_limit(client, res["user_id"]) == BASE + BONUS


# ── 한도 계산 ─────────────────────────────────────────────────────────────
def test_보상은_7일_동안_하루_몫에만_더한다(client):
    owner = member(client)
    _, link = _invite(client, owner)
    new = client.post("/signup", json={"phone": _phone(), "invite": link}).json()["user_id"]
    now = datetime.now(UTC)
    for _ in range(BASE + BONUS):
        usage.charge("course", subject=new, guest=False, now=now)
    with pytest.raises(usage.UsageDenied) as e:
        usage.charge("course", subject=new, guest=False, now=now)
    assert e.value.code == "daily_limit"
    later = now + timedelta(days=usage.INVITE_BONUS_DAYS, minutes=1)
    assert usage.member_limit("course", new, later) == BASE
    assert usage.invite_bonus_until(new, later) is None
    assert usage.member_limit("search", new, now) == usage.LIMITS["search"].member  # 보상 없는 기능


# ── 관리자 지표 ───────────────────────────────────────────────────────────
def test_관리자_지표는_출처별_체험_가입과_초대를_센다(client):
    owner = member(client)
    _, link = _invite(client, owner)
    client.post("/auth/guest", json={"agreed": True, "source": "instagram"})
    client.post("/auth/guest", json={"agreed": True, "source": "instagram"})
    client.post("/auth/guest", json={"agreed": True, "invite": link})
    _kakao(client, _kid(), invite=link)
    client.post("/signup", json={"phone": _phone(), "source": "threads"})

    body = client.get("/admin/growth").json()
    assert body["reward_rule"]["cap_per_inviter"] == INVITE_REWARD_CAP
    for window in ("7d", "30d"):
        w = body["windows"][window]
        assert w["guests_by_source"] == {"instagram": 2, "invite": 1}
        assert w["signups_by_source"]["invite"] == 1 and w["signups_by_source"]["threads"] == 1
        assert w["signups_by_source"]["direct"] >= 1  # 초대자(출처 없이 가입)
        assert w["invite_signups"] == 1
        assert w["rewards_granted"] == 1
        assert w["invites_sent"] >= 1


def test_관리자_지표는_토큰을_본다(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "s3cret")
    assert client.get("/admin/growth").status_code == 401
    assert client.get("/admin/growth", headers={"X-Admin-Token": "s3cret"}).status_code == 200


# ── 링크 미리보기 ─────────────────────────────────────────────────────────
def test_미리보기는_열람으로_세지_않는다(client):
    from app.funnel import funnel_store

    owner = member(client)
    cid, link = _invite(client, owner)
    body = client.get(f"/together/{link}/preview").json()
    assert body == {"owner_name": "나", "request_text": "토요일 3시 성수", "built": False, "region": None, "stops": 0}
    assert not [e for e in funnel_store.events() if e.name == "link_opened" and e.course_id == cid]
    assert client.get("/together/nope/preview").status_code == 404
    status = client.get(f"/together/{link}").json()
    assert status["invite_reward"]["extra"]["course"] == BONUS


# ── DB 경로 ───────────────────────────────────────────────────────────────
@pytest.fixture
def db(tmp_path, monkeypatch):
    import app.db as db_mod

    monkeypatch.setattr(settings, "database_url", f"sqlite:///{tmp_path}/r.db")
    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_SessionLocal", None)
    assert db_mod.init_db() is True
    db_mod.set_ready(True)
    yield db_mod
    db_mod.set_ready(False)


def test_DB_에_남고_같은_새_회원은_한_번만(client, db):
    owner = member(client)
    cid, link = _invite(client, owner)
    guest = client.post("/auth/guest", json={"agreed": True, "invite": link, "source": "Kakao"}).json()["user_id"]
    res = _kakao(client, _kid(), headers=H(guest))
    assert res["invite_reward"] is not None
    new = res["user_id"]
    acq = referral_store.get(new)
    assert acq.source == "kakao" and acq.inviter_id == owner and acq.course_id == cid
    assert referral_store.get(guest) is None
    assert _course_limit(client, owner) == BASE + BONUS
    # 같은 키로 한 번 더 넣으려 해도 유니크 제약으로 막힌다(동시 요청 대비)
    from app.referrals import Reward, identity_key, utcnow

    dup = Reward(identity_key(f"kakao:{_kid()}"), new, owner, cid, utcnow())
    assert referral_store.add_reward(dup) is True
    assert referral_store.add_reward(dup) is False
    w = client.get("/admin/growth").json()["windows"]["7d"]
    assert w["signups_by_source"] == {"kakao": 1, "direct": 1}
    assert w["rewards_granted"] == 2


def test_기존_DB_에도_새_테이블만_더해진다(tmp_path, monkeypatch):
    """운영 Postgres 처럼 users 가 이미 있는 DB: create_all 이 새 테이블 두 개를 더하고 기존 표는 건드리지 않는다.
    (기존 테이블에 칸을 더하지 않으므로 ALTER 보정이 필요 없다)"""
    import sqlalchemy as sa

    import app.db as db_mod

    url = f"sqlite:///{tmp_path}/old.db"
    old = sa.create_engine(url)
    with old.begin() as conn:
        conn.execute(sa.text("CREATE TABLE users (id VARCHAR PRIMARY KEY, phone VARCHAR)"))
        conn.execute(sa.text("INSERT INTO users (id, phone) VALUES ('u1', 'kakao:1')"))
    old.dispose()

    monkeypatch.setattr(settings, "database_url", url)
    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_SessionLocal", None)
    assert db_mod.init_db() is True
    insp = sa.inspect(db_mod._engine)
    assert {"user_acquisition", "invite_rewards"} <= set(insp.get_table_names())
    assert {c["name"] for c in insp.get_columns("users")} == {"id", "phone"}  # 기존 표는 그대로
    with db_mod._engine.connect() as conn:
        assert conn.execute(sa.text("SELECT phone FROM users WHERE id = 'u1'")).scalar() == "kakao:1"
    db_mod._engine.dispose()
