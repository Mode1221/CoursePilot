"""유료 외부 API 의 월 무료 한도 관리.

무료 한도를 넘는 순간 카드로 청구되는 API 가 있다(Google Places 가 대표적).
그래서 "얼마나 썼는지"를 세는 데서 그치지 않고, 한도에 닿으면 호출 자체를
거절한다 — 초과 요금은 사용자가 알아채기 전에 발생하기 때문이다.

인메모리이므로 인스턴스별 카운터다. 다중 인스턴스에서는 한도를 인스턴스 수로
나눠 잡는 것을 전제로 한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

# API 이름 → 월 무료 한도(콜 수). 없는 이름은 무제한으로 본다(카카오·LOCALDATA 등).
MONTHLY_FREE_LIMITS: dict[str, int] = {
    "google.hours": 5_000,  # Place Details (Pro)
    "google.rating": 1_000,  # Place Details (Enterprise)
    "google.map_id": 10_000,  # Text Search IDs-only (사실상 무료지만 상한을 둔다)
    "naver.directions": 60_000,
}

WARN_RATIO = 0.8  # 이 비율을 넘으면 경고(남은 한도로 월말까지 버틸 수 있는지 보라는 신호)


def _month_key(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).strftime("%Y-%m")


@dataclass
class _Counter:
    month: str
    used: int = 0


class QuotaStore:
    """월 단위 사용량 카운터. 달이 바뀌면 자동으로 0 부터 다시 센다."""

    def __init__(self) -> None:
        self._counters: dict[str, _Counter] = {}

    def limit(self, name: str) -> int | None:
        return MONTHLY_FREE_LIMITS.get(name)

    def used(self, name: str, now: datetime | None = None) -> int:
        counter = self._counters.get(name)
        if counter is None or counter.month != _month_key(now):
            return 0
        return counter.used

    def remaining(self, name: str, now: datetime | None = None) -> int | None:
        limit = self.limit(name)
        if limit is None:
            return None
        return max(0, limit - self.used(name, now))

    def allow(self, name: str, now: datetime | None = None) -> bool:
        """이번 호출이 무료 한도 안인지. 한도를 모르면 항상 허용."""
        remaining = self.remaining(name, now)
        return remaining is None or remaining > 0

    def record(self, name: str, count: int = 1, now: datetime | None = None) -> None:
        month = _month_key(now)
        counter = self._counters.get(name)
        if counter is None or counter.month != month:
            counter = _Counter(month=month)
            self._counters[name] = counter
        counter.used += count

    def snapshot(self, now: datetime | None = None) -> list[dict]:
        """한도가 정해진 API 의 사용량(관리 화면·경보용)."""
        rows = []
        for name, limit in sorted(MONTHLY_FREE_LIMITS.items()):
            used = self.used(name, now)
            rows.append(
                {
                    "name": name,
                    "used": used,
                    "limit": limit,
                    "remaining": max(0, limit - used),
                    "ratio": round(used / limit, 4) if limit else 0.0,
                }
            )
        return rows

    def alerts(self, now: datetime | None = None) -> list[dict]:
        """한도의 80% 를 넘긴 API(다음 달까지 못 버틸 수 있다)."""
        return [
            {"kind": "quota", "target": row["name"], "value": row["ratio"]}
            for row in self.snapshot(now)
            if row["ratio"] >= WARN_RATIO
        ]

    def clear(self) -> None:
        self._counters.clear()


quota_store = QuotaStore()
