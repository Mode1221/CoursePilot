"""합의 코스 측정 — 포트폴리오의 증거가 되는 숫자.

실험 지표(06-validation/experiment-design.md):
- 상대 입력 완료율 = 카드 낸 상대 / 링크 연 상대
- 합의 시간 = 상대 카드 → 둘 다 수락
- 확정률, 다녀옴
- **역할 역전** = 상대로만 참여했던 기기가 나중에 스스로 코스를 시작
- 30일 재사용 = 같은 시작자가 30일 안에 두 번째 합의 코스
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.db import is_ready

EVENTS = (
    "started",  # 시작한 사람이 링크를 만듦
    "link_opened",  # 상대가 링크를 처음 엶(코스당 1회)
    "partner_card",  # 상대 카드 첫 제출
    "owner_card",
    "card_edited",  # 코스를 만든 뒤 카드 수정
    "built",  # 합쳐서 코스 생성(meta: 둘 다 냈는지)
    "built_both",
    "accepted",
    "confirmed",  # 둘 다 수락
    "completed",  # 다녀왔어요
)


@dataclass
class Event:
    name: str
    course_id: str
    actor: str | None
    device_id: str | None
    user_id: str | None
    at: datetime


class FunnelStore:
    def __init__(self) -> None:
        self._mem: list[Event] = []

    def record(
        self,
        name: str,
        course_id: str,
        actor: str | None = None,
        device_id: str | None = None,
        user_id: str | None = None,
        once: bool = False,
        at: datetime | None = None,
    ) -> bool:
        """once=True 면 (name, course_id[, actor]) 가 이미 있으면 기록하지 않는다. 기록했으면 True."""
        if name not in EVENTS:
            raise ValueError(name)
        if once and self._exists(name, course_id, actor):
            return False
        ev = Event(name, course_id, actor, (device_id or None) and device_id[:64], user_id, at or datetime.now())
        if is_ready():
            from app.db import SessionLocal
            from app.models import FunnelEventModel

            with SessionLocal() as s:
                s.add(FunnelEventModel(name=ev.name, course_id=ev.course_id, actor=ev.actor,
                                       device_id=ev.device_id, user_id=ev.user_id, at=ev.at))
                s.commit()
        else:
            self._mem.append(ev)
        return True

    def _exists(self, name: str, course_id: str, actor: str | None) -> bool:
        return any(e.name == name and e.course_id == course_id and (actor is None or e.actor == actor)
                   for e in self.events())

    def events(self, since: datetime | None = None) -> list[Event]:
        if is_ready():
            from sqlalchemy import select

            from app.db import SessionLocal
            from app.models import FunnelEventModel

            with SessionLocal() as s:
                q = select(FunnelEventModel)
                if since:
                    q = q.where(FunnelEventModel.at >= since)
                rows = s.execute(q).scalars().all()
                return [Event(r.name, r.course_id, r.actor, r.device_id, r.user_id, r.at) for r in rows]
        return [e for e in self._mem if since is None or e.at >= since]

    def reset(self) -> None:  # 테스트용
        self._mem.clear()


funnel_store = FunnelStore()


def summarize(events: list[Event], now: datetime | None = None) -> dict:
    """퍼널·시간·역할 역전·재사용. 비율은 분모가 0이면 None."""
    now = now or datetime.now()
    by: dict[str, set[str]] = {n: set() for n in EVENTS}
    first_at: dict[tuple[str, str], datetime] = {}
    for e in sorted(events, key=lambda x: x.at):
        by[e.name].add(e.course_id)
        first_at.setdefault((e.name, e.course_id), e.at)

    def rate(a: str, b: str) -> float | None:
        return round(len(by[a]) / len(by[b]), 3) if by[b] else None

    def minutes(a: str, b: str) -> float | None:
        xs = [
            (first_at[(b, c)] - first_at[(a, c)]).total_seconds() / 60
            for c in by[a] & by[b]
            if first_at[(b, c)] >= first_at[(a, c)]
        ]
        return round(statistics.median(xs), 1) if xs else None

    # 역할 역전: 상대 카드를 냈던 기기가, 그 뒤에 시작자로 코스를 시작
    partner_dev = {}
    for e in events:
        if e.name == "partner_card" and e.device_id:
            partner_dev.setdefault(e.device_id, e.at)
    reversals = {
        e.device_id for e in events
        if e.name == "started" and e.device_id in partner_dev and e.at > partner_dev[e.device_id]
    }
    # 30일 재사용: 같은 시작자(사용자 id, 없으면 기기)가 30일 안에 두 번째 시작
    starts: dict[str, list[datetime]] = {}
    for e in events:
        if e.name == "started":
            key = e.user_id or e.device_id
            if key:
                starts.setdefault(key, []).append(e.at)
    repeaters = sum(
        1 for ts in starts.values() if len(ts) >= 2 and (sorted(ts)[1] - sorted(ts)[0]) <= timedelta(days=30)
    )
    return {
        "counts": {n: len(by[n]) for n in EVENTS},
        "rates": {
            "link_open_rate": rate("link_opened", "started"),
            "partner_card_rate": rate("partner_card", "link_opened"),  # 핵심: 30초가 진짜 30초인가
            "built_both_rate": rate("built_both", "built"),
            "confirmed_rate": rate("confirmed", "built"),
            "completed_rate": rate("completed", "confirmed"),
        },
        "median_minutes": {
            "start_to_partner_card": minutes("started", "partner_card"),
            "partner_card_to_confirmed": minutes("partner_card", "confirmed"),  # 합의 시간
        },
        "role_reversals": len(reversals),  # 입력만 하던 쪽이 먼저 시작한 횟수
        "partners_seen": len(partner_dev),
        "repeat_starters_30d": repeaters,
        "starters": len(starts),
    }
