"""유입 경로(첫 방문 출처)와 초대 보상.

**유입 경로**: 처음 들어온 주소의 `src`·`utm_source`(와 `utm_campaign`)를 프론트가 기억했다가
체험 시작·가입 때 보낸다. 사람마다 **처음 한 번만** 남긴다(first-touch) — 나중에 다른 광고로
다시 와도 덮어쓰지 않는다. 값은 소문자 `[a-z0-9_-]` 32자까지만 받는다(그 밖의 글자는 버린다).
같이 정하기 링크로 온 사람은 출처를 따로 적지 않았으면 `invite` 로 남긴다.

**초대 보상**: 같이 정하기 링크를 받은 사람이 **새 회원**이 되면, 링크를 만든 사람(코스 주인)과
새 회원 모두 7일 동안 하루 몫이 늘어난다(값은 `usage.INVITE_BONUS`). 어뷰징을 막는 규칙:
- 초대자는 클라이언트가 적어 보낸 id 가 아니라 **링크 토큰으로 찾은 코스의 주인**이다.
  코스 주인은 서버가 서명 토큰으로 확인한 신원으로만 정해진다(`identity.require_caller`).
- 이미 있던 회원이 다시 로그인한 것은 보상이 없다(계정을 새로 만들 때만).
- 초대자 자신(같은 계정, 또는 초대자였던 체험 계정을 옮겨 온 가입)은 보상이 없다.
- 새 회원 한 사람당 한 번. 로그인 수단(카카오 회원번호·전화번호)을 서명 키로 해시한 값으로
  세므로, 탈퇴하고 같은 카카오로 다시 가입해도 두 번 받지 못한다.
- 초대자 한 사람당 30일에 5번까지.
- 운영 자동 QA 요청은 보상도 유입 통계도 남기지 않는다(`qa.learning_on()`).

저장은 다른 스토어처럼 DB 가 있으면 테이블(`user_acquisition`, `invite_rewards`), 없으면 인메모리.
"""
from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

from app.config import settings
from app.db import is_ready

SOURCE_INVITE = "invite"
SOURCE_DIRECT = "direct"  # 출처 없이 들어온 사람(집계 표시용 — 저장은 None)
SOURCE_MAX_LEN = 32
INVITE_REWARD_CAP = 5  # 초대자 한 사람이 받을 수 있는 보상 수
INVITE_REWARD_WINDOW_DAYS = 30  # ↑ 를 세는 기간

_NOT_ALLOWED = re.compile(r"[^a-z0-9_-]")


def clean_source(value: str | None) -> str | None:
    """출처 값 정리: 소문자, `[a-z0-9_-]` 만, 32자까지. 남는 게 없으면 None."""
    if not value:
        return None
    cleaned = _NOT_ALLOWED.sub("", value.strip().lower())[:SOURCE_MAX_LEN]
    return cleaned or None


def utcnow() -> datetime:
    """DB 의 다른 시각 칸과 같이 tz 없는 UTC."""
    return datetime.now(UTC).replace(tzinfo=None)


def identity_key(login_identity: str) -> str:
    """로그인 수단(카카오 회원번호·전화번호)을 원문 없이 비교하기 위한 해시."""
    key = (settings.session_secret or "dev").encode()
    return hmac.new(key, f"invitee:{login_identity}".encode(), hashlib.sha256).hexdigest()[:32]


@dataclass
class Acquisition:
    user_id: str
    source: str | None = None
    campaign: str | None = None
    inviter_id: str | None = None  # 같이 정하기 링크를 만든 사람(서버가 코스에서 찾은 값)
    course_id: str | None = None
    guest_at: datetime | None = None  # 체험을 시작한 시각
    member_at: datetime | None = None  # 새 회원이 된 시각(기존 회원 로그인은 없음)


@dataclass
class Reward:
    invitee_key: str
    invitee_id: str
    inviter_id: str
    course_id: str | None
    created_at: datetime


class ReferralStore:
    def __init__(self) -> None:
        self._acq: dict[str, Acquisition] = {}
        self._rewards: list[Reward] = []

    # ── 유입 경로 ─────────────────────────────────────────────────────────
    def get(self, user_id: str) -> Acquisition | None:
        if is_ready():
            from app.db import SessionLocal
            from app.models import AcquisitionModel

            with SessionLocal() as s:
                row = s.get(AcquisitionModel, user_id)
                return _to_acq(row) if row is not None else None
        acq = self._acq.get(user_id)
        return replace(acq) if acq else None

    def save(self, acq: Acquisition) -> None:
        if is_ready():
            from app.db import SessionLocal
            from app.models import AcquisitionModel

            with SessionLocal() as s:
                row = s.get(AcquisitionModel, acq.user_id)
                if row is None:
                    row = AcquisitionModel(user_id=acq.user_id)
                    s.add(row)
                row.source = acq.source
                row.campaign = acq.campaign
                row.inviter_id = acq.inviter_id
                row.course_id = acq.course_id
                row.guest_at = acq.guest_at
                row.member_at = acq.member_at
                s.commit()
            return
        self._acq[acq.user_id] = replace(acq)

    def forget(self, user_id: str) -> None:
        """계정을 지울 때 유입 기록도 지운다. 보상 기록(해시만 있음)은 재보상 방지를 위해 남긴다."""
        if is_ready():
            from sqlalchemy import delete

            from app.db import SessionLocal
            from app.models import AcquisitionModel

            with SessionLocal() as s:
                s.execute(delete(AcquisitionModel).where(AcquisitionModel.user_id == user_id))
                s.commit()
            return
        self._acq.pop(user_id, None)

    def move(self, guest_id: str, member_id: str) -> None:
        """체험 계정을 회원으로 옮길 때: 유입 기록(회원에게 없을 때만 — first-touch)과
        초대자로서 받은 보상을 회원에게 넘긴다."""
        guest = self.get(guest_id)
        if guest is not None:
            if self.get(member_id) is None:
                self.save(replace(guest, user_id=member_id))
            self.forget(guest_id)
        if is_ready():
            from sqlalchemy import update

            from app.db import SessionLocal
            from app.models import InviteRewardModel

            with SessionLocal() as s:
                s.execute(
                    update(InviteRewardModel)
                    .where(InviteRewardModel.inviter_id == guest_id)
                    .values(inviter_id=member_id)
                )
                s.commit()
            return
        for r in self._rewards:
            if r.inviter_id == guest_id:
                r.inviter_id = member_id

    # ── 보상 ──────────────────────────────────────────────────────────────
    def rewarded(self, invitee_key: str) -> bool:
        if is_ready():
            from sqlalchemy import select

            from app.db import SessionLocal
            from app.models import InviteRewardModel

            with SessionLocal() as s:
                q = select(InviteRewardModel.id).where(InviteRewardModel.invitee_key == invitee_key)
                return s.execute(q).first() is not None
        return any(r.invitee_key == invitee_key for r in self._rewards)

    def count_for_inviter(self, inviter_id: str, since: datetime) -> int:
        if is_ready():
            from sqlalchemy import func, select

            from app.db import SessionLocal
            from app.models import InviteRewardModel

            with SessionLocal() as s:
                q = select(func.count(InviteRewardModel.id)).where(
                    InviteRewardModel.inviter_id == inviter_id, InviteRewardModel.created_at >= since
                )
                return int(s.execute(q).scalar() or 0)
        return sum(1 for r in self._rewards if r.inviter_id == inviter_id and r.created_at >= since)

    def add_reward(self, reward: Reward) -> bool:
        """보상 한 건을 남긴다. 같은 새 회원이 이미 받았으면(동시 요청 포함) False."""
        if is_ready():
            from sqlalchemy.exc import IntegrityError

            from app.db import SessionLocal
            from app.models import InviteRewardModel

            with SessionLocal() as s:
                s.add(
                    InviteRewardModel(
                        invitee_key=reward.invitee_key,
                        invitee_id=reward.invitee_id,
                        inviter_id=reward.inviter_id,
                        course_id=reward.course_id,
                        created_at=reward.created_at,
                    )
                )
                try:
                    s.commit()
                except IntegrityError:
                    s.rollback()
                    return False
            return True
        if self.rewarded(reward.invitee_key):
            return False
        self._rewards.append(replace(reward))
        return True

    def last_reward_at(self, user_id: str) -> datetime | None:
        """초대자든 새 회원이든 이 사람이 받은 마지막 보상 시각."""
        if is_ready():
            from sqlalchemy import func, or_, select

            from app.db import SessionLocal
            from app.models import InviteRewardModel

            with SessionLocal() as s:
                q = select(func.max(InviteRewardModel.created_at)).where(
                    or_(InviteRewardModel.inviter_id == user_id, InviteRewardModel.invitee_id == user_id)
                )
                return s.execute(q).scalar()
        times = [r.created_at for r in self._rewards if user_id in (r.inviter_id, r.invitee_id)]
        return max(times) if times else None

    # ── 집계(관리자) ──────────────────────────────────────────────────────
    def acquisitions_since(self, since: datetime) -> list[Acquisition]:
        if is_ready():
            from sqlalchemy import or_, select

            from app.db import SessionLocal
            from app.models import AcquisitionModel

            with SessionLocal() as s:
                q = select(AcquisitionModel).where(
                    or_(AcquisitionModel.guest_at >= since, AcquisitionModel.member_at >= since)
                )
                return [_to_acq(r) for r in s.execute(q).scalars().all()]
        return [
            replace(a)
            for a in self._acq.values()
            if (a.guest_at and a.guest_at >= since) or (a.member_at and a.member_at >= since)
        ]

    def rewards_since(self, since: datetime) -> int:
        if is_ready():
            from sqlalchemy import func, select

            from app.db import SessionLocal
            from app.models import InviteRewardModel

            with SessionLocal() as s:
                q = select(func.count(InviteRewardModel.id)).where(InviteRewardModel.created_at >= since)
                return int(s.execute(q).scalar() or 0)
        return sum(1 for r in self._rewards if r.created_at >= since)

    def clear(self) -> None:  # 테스트용
        self._acq.clear()
        self._rewards.clear()


def _to_acq(row) -> Acquisition:
    return Acquisition(
        user_id=row.user_id,
        source=row.source,
        campaign=row.campaign,
        inviter_id=row.inviter_id,
        course_id=row.course_id,
        guest_at=row.guest_at,
        member_at=row.member_at,
    )


referral_store = ReferralStore()


# ── 규칙 ──────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Arrival:
    """가입·체험 요청에 함께 온 유입 정보(클라이언트 값 — 정리해서 쓴다)."""

    source: str | None = None
    campaign: str | None = None
    invite: str | None = None  # 같이 정하기 링크 토큰


def _tracking_on() -> bool:
    from app.qa import learning_on

    return learning_on()


def resolve_invite(token: str | None) -> tuple[str, str] | None:
    """링크 토큰 → (초대자 id, 코스 id). 초대자는 코스 주인(서명 신원으로 정해진 값)."""
    if not token or len(token) > 64:
        return None
    from app.store import store

    course = store.find_by_together_token(token)
    if course is None or course.together is None or not course.owner_id:
        return None
    return course.owner_id, course.id


def record_guest(user_id: str, arrival: Arrival, now: datetime | None = None) -> None:
    """체험 계정을 만들 때 첫 방문 출처를 남긴다."""
    if not _tracking_on():
        return
    invite = resolve_invite(arrival.invite)
    source = clean_source(arrival.source) or (SOURCE_INVITE if invite else None)
    referral_store.save(
        Acquisition(
            user_id=user_id,
            source=source,
            campaign=clean_source(arrival.campaign),
            inviter_id=invite[0] if invite else None,
            course_id=invite[1] if invite else None,
            guest_at=now or utcnow(),
        )
    )


def on_new_member(
    member_id: str,
    login_identity: str,
    arrival: Arrival,
    merged_guest_id: str | None = None,
    now: datetime | None = None,
) -> dict | None:
    """새 회원이 생겼을 때(계정을 방금 만들었을 때만 부른다). 유입을 남기고, 초대로 왔으면 보상.

    체험 계정을 옮겨 온 경우 그 체험의 유입 기록이 이미 회원에게 넘어와 있다(`move`) — 첫 출처를 지킨다.
    보상을 줬으면 화면에 보여 줄 내용을, 아니면 None.
    """
    if not _tracking_on():
        return None
    now = now or utcnow()
    acq = referral_store.get(member_id) or Acquisition(user_id=member_id)
    if acq.inviter_id is None:
        invite = resolve_invite(arrival.invite)
        if invite:
            acq.inviter_id, acq.course_id = invite
    if acq.source is None and acq.guest_at is None:  # 체험 때 남긴 게 없을 때만(first-touch)
        acq.source = clean_source(arrival.source)
        acq.campaign = clean_source(arrival.campaign)
    if acq.source is None and acq.inviter_id:
        acq.source = SOURCE_INVITE
    acq.member_at = acq.member_at or now
    referral_store.save(acq)
    return _grant(acq, member_id, login_identity, merged_guest_id, now)


def _grant(
    acq: Acquisition, member_id: str, login_identity: str, merged_guest_id: str | None, now: datetime
) -> dict | None:
    from app.qa import QA_PHONE
    from app.usage import INVITE_BONUS, INVITE_BONUS_DAYS
    from app.users import user_store

    inviter_id = acq.inviter_id
    if not inviter_id or inviter_id in (member_id, merged_guest_id):
        return None  # 초대로 오지 않았거나, 자기 링크로 자기 새 계정을 만든 경우
    inviter = user_store.get(inviter_id)
    if inviter is None or inviter.phone == QA_PHONE:
        return None
    key = identity_key(login_identity)
    if referral_store.rewarded(key):
        return None
    since = now - timedelta(days=INVITE_REWARD_WINDOW_DAYS)
    if referral_store.count_for_inviter(inviter_id, since) >= INVITE_REWARD_CAP:
        return None
    reward = Reward(
        invitee_key=key,
        invitee_id=member_id,
        inviter_id=inviter_id,
        course_id=acq.course_id,
        created_at=now,
    )
    if not referral_store.add_reward(reward):
        return None
    return {"days": INVITE_BONUS_DAYS, "extra": dict(INVITE_BONUS)}


def reward_offer() -> dict:
    """초대 화면에 보여 줄 보상 내용(값의 출처를 서버 하나로)."""
    from app.usage import INVITE_BONUS, INVITE_BONUS_DAYS

    return {"days": INVITE_BONUS_DAYS, "extra": dict(INVITE_BONUS)}


def growth_stats(now: datetime | None = None) -> dict:
    """최근 7·30일 체험·가입의 출처별 수, 보낸 초대, 초대로 온 가입, 준 보상. 개인정보 없음."""
    from app.funnel import funnel_store

    now = now or utcnow()
    local_now = datetime.now()
    out: dict = {}
    for days in (7, 30):
        since = now - timedelta(days=days)
        guests: dict[str, int] = {}
        signups: dict[str, int] = {}
        invite_signups = 0
        for a in referral_store.acquisitions_since(since):
            src = a.source or SOURCE_DIRECT
            if a.guest_at and a.guest_at >= since:
                guests[src] = guests.get(src, 0) + 1
            if a.member_at and a.member_at >= since:
                signups[src] = signups.get(src, 0) + 1
                if a.inviter_id:
                    invite_signups += 1
        # 퍼널 이벤트 시각은 서버 지역 시각이다(funnel.py) — 같은 기준으로 자른다
        events = funnel_store.events(since=local_now - timedelta(days=days))
        out[f"{days}d"] = {
            "guests": sum(guests.values()),
            "signups": sum(signups.values()),
            "guests_by_source": dict(sorted(guests.items(), key=lambda kv: -kv[1])),
            "signups_by_source": dict(sorted(signups.items(), key=lambda kv: -kv[1])),
            "invites_sent": len({e.course_id for e in events if e.name == "started"}),
            "invite_opens": len({e.course_id for e in events if e.name == "link_opened"}),
            "invite_signups": invite_signups,
            "rewards_granted": referral_store.rewards_since(since),
        }
    return out
