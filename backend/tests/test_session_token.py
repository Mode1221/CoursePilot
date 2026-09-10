"""세션 토큰: id 만으로는 남의 계정이 되지 않는다."""
from __future__ import annotations

import itertools

import pytest
from fastapi.testclient import TestClient

import app.config as cfg
from app.main import api
from app.session_token import enabled, issue, verify

client = TestClient(api)
_phones = itertools.count(1)


@pytest.fixture()
def secret(monkeypatch):
    monkeypatch.setattr(cfg.settings, "session_secret", "test-secret")
    yield


def _signup() -> dict:
    return client.post("/signup", json={"phone": f"010-9090-{next(_phones):04d}"}).json()


def test_비밀키가_없으면_종전대로_동작한다():
    assert enabled() is False
    assert verify("u1", None) is True  # 개발 환경은 헤더를 믿는다
    assert issue("u1") == ""


def test_토큰은_사용자마다_다르다(secret):
    assert issue("u1") != issue("u2")
    assert verify("u1", issue("u1"))
    assert not verify("u1", issue("u2"))


def test_가입하면_토큰을_준다(secret):
    body = _signup()
    assert body["token"] and verify(body["user_id"], body["token"])


def test_토큰_없이는_개인_데이터를_못_본다(secret):
    body = _signup()
    uid = body["user_id"]
    headers = {"X-User-Id": uid}
    assert client.get(f"/users/{uid}/credits", headers=headers).status_code == 401
    with_token = {**headers, "X-User-Token": body["token"]}
    assert client.get(f"/users/{uid}/credits", headers=with_token).status_code == 200


def test_남의_토큰으로는_통과하지_못한다(secret):
    mine, other = _signup(), _signup()
    headers = {"X-User-Id": mine["user_id"], "X-User-Token": other["token"]}
    assert client.get(f"/users/{mine['user_id']}/credits", headers=headers).status_code == 401


def test_계정_삭제도_토큰을_요구한다(secret):
    body = _signup()
    uid = body["user_id"]
    assert client.delete(f"/users/{uid}", headers={"X-User-Id": uid}).status_code == 401


def test_토큰이_맞으면_계정_삭제가_된다(secret):
    body = _signup()
    uid = body["user_id"]
    headers = {"X-User-Id": uid, "X-User-Token": body["token"]}
    assert client.delete(f"/users/{uid}", headers=headers).status_code == 200


def test_내_코스_목록도_토큰을_본다(secret):
    body = _signup()
    uid, token = body["user_id"], body["token"]
    assert client.get(f"/users/{uid}/courses", headers={"X-User-Id": uid}).status_code == 401
    ok = client.get(
        f"/users/{uid}/courses", headers={"X-User-Id": uid, "X-User-Token": token}
    )
    assert ok.status_code == 200


def test_북마크도_토큰을_본다(secret):
    body = _signup()
    uid, token = body["user_id"], body["token"]
    assert client.get(f"/users/{uid}/bookmarks", headers={"X-User-Id": uid}).status_code == 401
    assert (
        client.get(
            f"/users/{uid}/bookmarks", headers={"X-User-Id": uid, "X-User-Token": token}
        ).status_code
        == 200
    )
