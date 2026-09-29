"""누가 요청했는가 — 게스트(체험)·회원·코스 편집 권한을 한곳에서 판정한다.

신원은 **서버가 발급한 서명 토큰**으로만 인정한다(X-User-Id + X-User-Token).
로그인이 없는 체험 사용자도 서버가 게스트 계정을 만들어 토큰을 준다 — 그래서
"로그인이 없다"와 "신원이 없다"가 다르다. 남의 id 를 헤더에 적어 사칭하는 길은 없다.

계정 종류는 users.phone 칸의 접두어로 구분한다(스키마 변경 없이):
- `guest:<id>`  — 체험 계정. 전화번호·카카오 없음. 가입하지 않으면 30일 뒤 지운다.
- `kakao:<카카오 회원번호>` — 카카오 로그인 회원.
- 숫자만 — 전화 인증 회원(기존).
전화번호 입력은 숫자·하이픈만 받으므로(`_PhoneBody`) 접두어와 겹칠 수 없다.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass

from fastapi import HTTPException

from app.schemas import Course
from app.session_token import verify
from app.users import User, user_store

GUEST_PREFIX = "guest:"
KAKAO_PREFIX = "kakao:"


def is_guest(user: User) -> bool:
    return user.phone.startswith(GUEST_PREFIX)


def kind_of(user: User) -> str:
    return "guest" if is_guest(user) else "member"


@dataclass(frozen=True)
class Caller:
    user_id: str
    guest: bool

    @property
    def kind(self) -> str:
        return "guest" if self.guest else "member"


def resolve_caller(user_id: str | None, token: str | None) -> Caller | None:
    """서명이 맞는 실제 계정이면 Caller, 신원을 안 보냈으면 None.

    신원을 보냈는데 서명이 틀리면 401(재로그인). 서명은 맞는데 계정이 없으면(탈퇴·체험 만료)
    None — 다시 시작하게 한다.
    """
    if not user_id:
        return None
    if not verify(user_id, token):
        raise HTTPException(status_code=401, detail="다시 로그인해 주세요")
    user = user_store.get(user_id)
    if user is None:
        return None
    return Caller(user_id=user.id, guest=is_guest(user))


def require_caller(user_id: str | None, token: str | None) -> Caller:
    from app.usage import guest_required

    caller = resolve_caller(user_id, token)
    if caller is None:
        raise guest_required()
    return caller


def create_guest(nickname: str | None = None) -> User:
    from app.usage import LIMITS

    uid = secrets.token_urlsafe(8)
    # 과금 모드에서도 체험 AI 몫만큼은 크레딧이 있어야 체험이 막히지 않는다
    user = user_store.create(f"{GUEST_PREFIX}{uid}", credits_limit=LIMITS["ai"].guest)
    if nickname:
        prefs = user.preferences.model_copy(update={"nickname": nickname[:20]})
        user_store.set_preferences(user.id, prefs)
    return user


def course_editor(
    course: Course,
    user_id: str | None,
    user_token: str | None,
    together_token: str | None,
) -> str:
    """코스를 손으로 고칠 수 있는 사람인지. 생성자면 "owner", 합의 코스 상대면 "partner".

    코스 id 는 공유 링크로 누구에게나 간다 — id 만 알아서는 고칠 수 없어야 한다.
    """
    if together_token and course.together is not None:
        if token_matches(course.together.token, together_token):
            return "partner"
    if course.owner_id is not None and user_id == course.owner_id:
        if not verify(course.owner_id, user_token):
            raise HTTPException(status_code=401, detail="다시 로그인해 주세요")
        return "owner"
    raise HTTPException(status_code=403, detail="이 코스를 만든 사람이나 같이 정하는 상대만 고칠 수 있어요")


def token_matches(expected: str, given: str | None) -> bool:
    """상수 시간 비교. 헤더에 비 ASCII 가 오면 str 비교가 TypeError(500)라 바이트로 비교한다."""
    if not given:
        return False
    return secrets.compare_digest(expected.encode(), given.encode("utf-8", "ignore"))


def merge_guest(guest_id: str, member_id: str) -> int:
    """체험 때 만든 것을 로그인한 계정으로 옮기고 게스트 계정을 지운다. 옮긴 코스 수.

    가입해서 잃는 게 있으면 사람들은 가입하지 않는다 — 코스·같이 정한 기록·북마크·선호를 그대로 잇는다.
    """
    if guest_id == member_id:
        return 0
    guest = user_store.get(guest_id)
    if guest is None or not is_guest(guest):
        return 0

    from app.behavior import behavior_store
    from app.bookmarks import bookmark_store
    from app.couples import couple_store
    from app.referrals import referral_store
    from app.store import store
    from app.usage import forget_subject

    moved = 0
    for course in store.list_by_owner(guest_id, limit=1000):
        old_key = couple_key_for(course, guest_id)
        course.owner_id = member_id
        store.save(course)
        moved += 1
        new_key = couple_key_for(course, member_id)
        if old_key and new_key:
            st = couple_store.get(old_key)
            mine = couple_store.get(new_key)
            # 회원에게 같은 이름의 상대 기록이 이미 있으면 덮어쓰지 않는다(그쪽이 더 오래 쌓인 기록이다)
            if (st.courses or st.visited or st.ratings) and not (mine.courses or mine.visited or mine.ratings):
                couple_store.save(new_key, st)
    couple_store.delete_owner(guest_id)
    behavior_store.delete_user(guest_id)
    for cid in bookmark_store.list_course_ids(guest_id, limit=1000):
        bookmark_store.add(member_id, cid)
    bookmark_store.remove_all(guest_id)

    member = user_store.get(member_id)
    if member is not None and not _has_prefs(member) and _has_prefs(guest):
        user_store.set_preferences(member_id, guest.preferences)
    # 첫 방문 출처·초대 정보(와 초대자로서 받은 보상)도 잇는다 — 가입이 "새 유입"으로 둔갑하지 않게
    referral_store.move(guest_id, member_id)
    user_store.delete(guest_id)
    forget_subject(guest_id)
    return moved


def couple_key_for(course: Course, owner_id: str) -> str | None:
    from app.couples import couple_key

    t = course.together
    return couple_key(owner_id, t.partner_name) if t else None


def _has_prefs(user: User) -> bool:
    p = user.preferences
    return bool(p.mood or p.region or p.budget or p.transport or p.diet or p.must_haves)


def purge_guests(older_than_days: int = 30) -> dict:
    """가입하지 않은 체험 계정과 그 코스·대화를 지운다(개인정보 보관 기한). DB 전용."""
    from datetime import datetime, timedelta

    from sqlalchemy import select

    from app.behavior import behavior_store
    from app.bookmarks import bookmark_store
    from app.chat import chat_store
    from app.couples import couple_store
    from app.db import SessionLocal, is_ready
    from app.models import UserModel
    from app.referrals import referral_store
    from app.store import store
    from app.usage import counters, forget_subject

    if not is_ready():
        return {"guests": 0, "courses": 0, "counters": 0}
    cutoff = datetime.utcnow() - timedelta(days=older_than_days)
    with SessionLocal() as s:
        ids = [
            r[0]
            for r in s.execute(
                select(UserModel.id).where(
                    UserModel.phone.startswith(GUEST_PREFIX), UserModel.created_at < cutoff
                )
            ).all()
        ]
    courses = 0
    for uid in ids:
        for course in store.list_by_owner(uid, limit=1000):
            store.delete(course.id)
            chat_store.clear(course.id)
            courses += 1
        bookmark_store.remove_all(uid)
        couple_store.delete_owner(uid)
        behavior_store.delete_user(uid)
        forget_subject(uid)
        referral_store.forget(uid)
        user_store.delete(uid)
    pruned = counters.prune()
    return {"guests": len(ids), "courses": courses, "counters": pruned}
