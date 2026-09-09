"""회원 탈퇴 — 계정·코스·대화·북마크를 지운다."""
from __future__ import annotations

import itertools

from fastapi.testclient import TestClient

from app.main import api

client = TestClient(api)
_phones = itertools.count(1)


def _user_with_course() -> tuple[str, str, str]:
    phone = f"010-9292-{next(_phones):04d}"
    uid = client.post("/signup", json={"phone": phone}).json()["user_id"]
    cid = client.post("/courses", headers={"X-User-Id": uid}).json()["id"]
    client.post(
        f"/courses/{cid}/generate",
        headers={"X-User-Id": uid},
        json={"text": "성수동 오전 10시 5시간 도보"},
    )
    return uid, cid, phone


def test_탈퇴하면_계정과_코스가_사라진다():
    uid, cid, _ = _user_with_course()
    res = client.delete(f"/users/{uid}", headers={"X-User-Id": uid})
    assert res.status_code == 200
    assert res.json()["deleted_courses"] >= 1
    assert client.get(f"/courses/{cid}").status_code == 404
    assert client.get(f"/users/{uid}/credits", headers={"X-User-Id": uid}).status_code == 404


def test_대화_기록도_지운다():
    uid, cid, _ = _user_with_course()
    assert client.get(f"/courses/{cid}/messages").json()  # 대화가 남아 있다
    client.delete(f"/users/{uid}", headers={"X-User-Id": uid})
    assert client.get(f"/courses/{cid}/messages").json() == []


def test_북마크도_지운다():
    uid, cid, _ = _user_with_course()
    client.put(f"/users/{uid}/bookmarks/{cid}", headers={"X-User-Id": uid})
    client.delete(f"/users/{uid}", headers={"X-User-Id": uid})
    # 계정이 없으므로 조회 자체가 막힌다
    assert client.get(f"/users/{uid}/bookmarks", headers={"X-User-Id": uid}).json() == []


def test_남의_계정은_지울_수_없다():
    uid, _, _ = _user_with_course()
    other = client.post(
        "/signup", json={"phone": f"010-9393-{next(_phones):04d}"}
    ).json()["user_id"]
    assert client.delete(f"/users/{uid}", headers={"X-User-Id": other}).status_code == 403


def test_같은_번호로_다시_가입하면_새_계정():
    uid, _, phone = _user_with_course()
    client.delete(f"/users/{uid}", headers={"X-User-Id": uid})
    again = client.post("/signup", json={"phone": phone}).json()["user_id"]
    assert again != uid
