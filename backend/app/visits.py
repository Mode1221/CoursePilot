"""방문 세기 — 홍보 글을 본 사람이 실제로 들어왔는지(클릭 → 체험 시작 사이의 빈칸).

유입 출처는 체험을 시작할 때만 남아(app/referrals.py), 들어왔다가 그냥 나간 사람은 보이지 않았다.
그래서 **기기의 첫 방문 한 번**을 날짜·출처별 개수로만 센다. 프론트가 첫 방문(기기에 기록이 없을 때)에
`POST /visit` 를 한 번 보낸다.

- 개인정보 없음: 날짜·출처·개수만 저장한다. IP 는 같은 날 중복을 거르는 데만 메모리에서 해시로 쓰고 버린다.
- 부풀리기 방지: 같은 IP 는 하루에 출처당 한 번만 센다(메모리, 날짜가 바뀌면 비움).
- 운영 자동 QA 요청은 세지 않는다(`qa.learning_on()`).
"""
from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime, timedelta

from app.config import settings
from app.db import is_ready
from app.referrals import SOURCE_DIRECT, clean_source

KST = timedelta(hours=9)
MAX_SEEN = 50_000  # 하루 중복 거르기 메모리 상한 (넘으면 비우고 다시 — 약간 더 셀 수 있지만 메모리는 지킨다)


def kst_day(now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    return (now.astimezone(UTC) + KST).date().isoformat()


class VisitStore:
    def __init__(self) -> None:
        self._counts: dict[tuple[str, str], int] = {}
        self._seen: set[str] = set()
        self._seen_day = ""

    def _first_today(self, day: str, ip: str, source: str) -> bool:
        if day != self._seen_day or len(self._seen) >= MAX_SEEN:
            self._seen = set()
            self._seen_day = day
        key = hmac.new((settings.session_secret or "visit").encode(), f"{day}|{ip}|{source}".encode(), hashlib.sha256).hexdigest()[:24]
        if key in self._seen:
            return False
        self._seen.add(key)
        return True

    def record(self, source: str | None, ip: str, now: datetime | None = None) -> bool:
        """새 방문 한 건. 같은 IP·출처는 하루 한 번만. 센 경우 True."""
        day = kst_day(now)
        src = clean_source(source) or SOURCE_DIRECT
        if not self._first_today(day, ip, src):
            return False
        if is_ready():
            from sqlalchemy import update
            from sqlalchemy.exc import IntegrityError

            from app.db import SessionLocal
            from app.models import VisitDailyModel

            bump = update(VisitDailyModel).where(VisitDailyModel.day == day, VisitDailyModel.source == src).values(n=VisitDailyModel.n + 1)
            with SessionLocal() as s:
                if s.execute(bump).rowcount == 0:
                    s.add(VisitDailyModel(day=day, source=src, n=1))
                    try:
                        s.commit()
                        return True
                    except IntegrityError:  # 같은 순간 다른 요청이 먼저 만들었다 — 더하기로
                        s.rollback()
                        s.execute(bump)
                s.commit()
            return True
        self._counts[(day, src)] = self._counts.get((day, src), 0) + 1
        return True

    def since(self, first_day: str) -> list[tuple[str, str, int]]:
        """(날짜, 출처, 수) — first_day 부터."""
        if is_ready():
            from sqlalchemy import select

            from app.db import SessionLocal
            from app.models import VisitDailyModel

            with SessionLocal() as s:
                rows = s.execute(select(VisitDailyModel).where(VisitDailyModel.day >= first_day)).scalars()
                return [(r.day, r.source, r.n or 0) for r in rows]
        return [(d, src, n) for (d, src), n in self._counts.items() if d >= first_day]

    def clear(self) -> None:  # 테스트용
        self._counts.clear()
        self._seen = set()
        self._seen_day = ""


visit_store = VisitStore()
