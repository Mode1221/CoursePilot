"""로그인: 전화 인증 구멍 차단 · 카카오 로그인 · 체험 기록 이어받기 · 영속 카운터 · 체험 정리."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import api


@pytest.fixture
def client():
    return TestClient(api)


def _guest(client) -> str:
    return client.post("/auth/guest", json={"agreed": True}).json()["user_id"]


# ── 전화번호만으로 남의 계정에 들어가던 구멍 ───────────────────────────────
def test_운영에서_SMS_가_꺼져_있으면_가입이_거절된다(client, monkeypatch):
    from app.users import user_store

    victim = user_store.create("01012345678")
    monkeypatch.setattr(settings, "env", "production")
    monkeypatch.setattr(settings, "sms_dev_fallback", False)
    res = client.post("/signup", json={"phone": "010-1234-5678"})
    assert res.status_code == 403
    assert victim.id not in res.text


def test_운영_개발폴백으로는_기존_계정에_못_들어간다(client, monkeypatch):
    """개발 폴백은 인증번호를 화면에 보여 준다 — 남의 번호도 받아 맞힐 수 있다."""
    from app.auth import verification_store
    from app.users import user_store

    victim = user_store.create("01055556666")
    monkeypatch.setattr(settings, "env", "production")
    monkeypatch.setattr(settings, "sms_dev_fallback", True)
    code = client.post("/auth/sms/request", json={"phone": "010-5555-6666"}).json()["dev_code"]
    ok = client.post("/auth/sms/verify", json={"phone": "010-5555-6666", "code": code}).json()
    assert "token" not in ok and ok.get("user_id") != victim.id
    res = client.post("/signup", json={"phone": "010-5555-6666"})
    assert res.status_code == 409
    verification_store._verified.clear()


def test_개발에서는_지금처럼_바로_가입된다(client):
    res = client.post("/signup", json={"phone": "010-4444-0001"})
    assert res.status_code == 200
    assert res.json()["kind"] == "member"


def test_공개_설정은_운영_SMS_없으면_전화_로그인을_끈다(client, monkeypatch):
    monkeypatch.setattr(settings, "env", "production")
    assert client.get("/config/public").json()["phone_login"] is False


# ── 카카오 로그인 ─────────────────────────────────────────────────────────
@pytest.fixture
def kakao(monkeypatch):
    from app.adapters import kakao_auth

    monkeypatch.setattr(settings, "kakao_login_client_id", "login-app-key")
    monkeypatch.setattr(settings, "cors_origins", ["https://coursepilot.example"])
    calls: list[tuple[str, str]] = []

    async def fake(code: str, redirect_uri: str, client=None) -> str:
        calls.append((code, redirect_uri))
        if code == "bad":
            raise kakao_auth.KakaoLoginError("bad")
        return "4242"

    monkeypatch.setattr(kakao_auth, "kakao_user_id", fake)
    return calls


CB = "https://coursepilot.example/auth/kakao"


def test_카카오_로그인이_회원을_만들고_다시_오면_같은_계정(client, kakao):
    first = client.post("/auth/kakao", json={"code": "c1", "redirect_uri": CB}).json()
    again = client.post("/auth/kakao", json={"code": "c2", "redirect_uri": CB}).json()
    assert first["kind"] == "member"
    assert first["user_id"] == again["user_id"]


def test_카카오_실패는_400(client, kakao):
    assert client.post("/auth/kakao", json={"code": "bad", "redirect_uri": CB}).status_code == 400


@pytest.mark.parametrize(
    "uri",
    [
        "https://evil.example/auth/kakao",
        "https://coursepilot.example/other",
        "https://coursepilot.example/auth/kakao?next=x",
    ],
)
def test_돌아올_주소는_우리_콜백만(client, kakao, uri):
    assert client.post("/auth/kakao", json={"code": "c", "redirect_uri": uri}).status_code == 400
    assert kakao == []  # 카카오에 코드도 보내지 않는다


def test_키가_없으면_카카오_로그인은_503(client, monkeypatch):
    monkeypatch.setattr(settings, "kakao_login_client_id", "")
    assert client.post("/auth/kakao", json={"code": "c", "redirect_uri": CB}).status_code == 503


def test_체험_코스를_로그인한_계정으로_옮긴다(client, kakao):
    guest = _guest(client)
    cid = client.post("/courses", headers={"X-User-Id": guest}).json()["id"]
    res = client.post("/auth/kakao", json={"code": "c", "redirect_uri": CB}, headers={"X-User-Id": guest}).json()
    assert res["moved_courses"] == 1
    member = res["user_id"]
    assert client.get(f"/courses/{cid}").json()["owner_id"] == member
    mine = client.get(f"/users/{member}/courses", headers={"X-User-Id": member}).json()
    assert [c["id"] for c in mine] == [cid]
    # 게스트 계정은 사라진다
    assert client.get("/me", headers={"X-User-Id": guest}).json()["kind"] is None
    # 로그인한 뒤에는 회원 몫(IP 체험 상한과 무관)
    assert client.post("/courses", headers={"X-User-Id": member}).status_code == 200


def test_전화_가입도_체험_코스를_옮긴다(client):
    guest = _guest(client)
    cid = client.post("/courses", headers={"X-User-Id": guest}).json()["id"]
    res = client.post("/signup", json={"phone": "010-3131-0001"}, headers={"X-User-Id": guest}).json()
    assert res["moved_courses"] == 1
    assert client.get(f"/courses/{cid}").json()["owner_id"] == res["user_id"]


def test_남의_게스트_id_로는_옮기지_못한다(client, kakao, monkeypatch):
    monkeypatch.setattr(settings, "session_secret", "s" * 40)
    guest = client.post("/auth/guest", json={"agreed": True}).json()
    cid = client.post(
        "/courses", headers={"X-User-Id": guest["user_id"], "X-User-Token": guest["token"]}
    ).json()["id"]
    res = client.post(
        "/auth/kakao",
        json={"code": "c", "redirect_uri": CB},
        headers={"X-User-Id": guest["user_id"], "X-User-Token": "1.forged"},
    ).json()
    assert res["moved_courses"] == 0
    assert client.get(f"/courses/{cid}").json()["owner_id"] == guest["user_id"]


# ── 영속 카운터·체험 정리(DB 경로) ────────────────────────────────────────
@pytest.fixture
def db(tmp_path, monkeypatch):
    import app.db as db_mod

    monkeypatch.setattr(settings, "database_url", f"sqlite:///{tmp_path}/t.db")
    monkeypatch.setattr(db_mod, "_engine", None)
    monkeypatch.setattr(db_mod, "_SessionLocal", None)
    assert db_mod.init_db() is True
    db_mod.set_ready(True)
    yield db_mod
    db_mod.set_ready(False)


def test_카운터는_DB_에_남고_몫을_넘지_않는다(db):
    from app.usage import counters

    assert counters.take("d:2026-09-29:ai:x", 2)
    assert counters.take("d:2026-09-29:ai:x", 2)
    assert not counters.take("d:2026-09-29:ai:x", 2)
    counters.give_back("d:2026-09-29:ai:x")
    assert counters.used("d:2026-09-29:ai:x") == 1


def test_오래된_카운터는_지운다(db):
    from datetime import datetime

    from app.usage import KST, counters

    counters.take("d:2026-01-01:ai:x", 5)
    counters.take("g:2026-01-01:llm", 5)
    counters.take("d:2026-09-29:ai:x", 5)
    counters.take("t:ai:guest1", 5)  # 체험 몫은 날짜가 없어 남는다(게스트를 지울 때 함께 지운다)
    removed = counters.prune(keep_days=14, now=datetime(2026, 9, 29, tzinfo=KST))
    assert removed == 2
    assert counters.used("d:2026-09-29:ai:x") == 1
    assert counters.used("t:ai:guest1") == 1


def test_가입하지_않은_체험은_30일_뒤_지운다(db):
    from datetime import datetime, timedelta

    from app.db import SessionLocal
    from app.identity import create_guest, purge_guests
    from app.models import UserModel
    from app.store import store
    from app.users import user_store

    old = create_guest()
    fresh = create_guest()
    kept_member = user_store.create("01077778888")
    course = store.create(owner_id=old.id)
    with SessionLocal() as s:
        s.get(UserModel, old.id).created_at = datetime.utcnow() - timedelta(days=31)
        s.get(UserModel, kept_member.id).created_at = datetime.utcnow() - timedelta(days=90)
        s.commit()
    result = purge_guests(30)
    assert result["guests"] == 1 and result["courses"] == 1
    assert user_store.get(old.id) is None
    assert store.get(course.id) is None
    assert user_store.get(fresh.id) is not None
    assert user_store.get(kept_member.id) is not None


def test_이어받기가_회원의_기존_커플_기록을_덮어쓰지_않는다(client, kakao):
    from app.couples import couple_store

    member_id = client.post("/auth/kakao", json={"code": "c", "redirect_uri": CB}).json()["user_id"]
    mine = couple_store.get(f"{member_id}:상대")
    mine.courses = 5
    couple_store.save(f"{member_id}:상대", mine)

    guest = _guest(client)
    cid = client.post("/courses", headers={"X-User-Id": guest}).json()["id"]
    client.post(f"/courses/{cid}/together", json={"text": "토요일 3시 성수"}, headers={"X-User-Id": guest})
    theirs = couple_store.get(f"{guest}:상대")
    theirs.courses = 1
    couple_store.save(f"{guest}:상대", theirs)

    client.post("/auth/kakao", json={"code": "c", "redirect_uri": CB}, headers={"X-User-Id": guest})
    assert couple_store.get(f"{member_id}:상대").courses == 5
    assert couple_store.get(f"{guest}:상대").courses == 0  # 원본은 지운다
