"""테스트 공용: 코스는 이제 신원(회원·체험 계정)이 있어야 만들 수 있다."""
from __future__ import annotations

import itertools

_seq = itertools.count(1)


def member(client) -> str:
    """전화 가입 회원 id(개발 환경: SMS 없이 가입된다)."""
    phone = f"0109{9_000_000 + next(_seq):07d}"
    return client.post("/signup", json={"phone": phone}).json()["user_id"]


def owned_course(client, uid: str | None = None) -> tuple[str, str]:
    """회원 하나와 그 회원의 빈 코스. (user_id, course_id)"""
    uid = uid or member(client)
    cid = client.post("/courses", headers={"X-User-Id": uid}).json()["id"]
    return uid, cid
