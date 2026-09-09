"""유료 외부 API 의 월 무료 한도 관리.

무료 한도를 넘는 순간 카드로 청구되는 API 가 있다(Google Places 가 대표적).
그래서 "얼마나 썼는지"를 세는 데서 그치지 않고, 한도에 닿으면 호출 자체를
거절한다 — 초과 요금은 사용자가 알아채기 전에 발생하기 때문이다.

인메모리이므로 인스턴스별 카운터다. 다중 인스턴스에서는 한도를 인스턴스 수로
나눠 잡는 것을 전제로 한다.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

logger = logging.getLogger("coursepilot")

# API 이름 → 월 무료 한도(콜 수). 없는 이름은 무제한으로 본다(카카오·LOCALDATA 등).
MONTHLY_FREE_LIMITS: dict[str, int] = {
    "google.hours": 5_000,  # Place Details (Pro)
    "google.rating": 1_000,  # Place Details (Enterprise)
    "google.map_id": 10_000,  # Text Search IDs-only (사실상 무료지만 상한을 둔다)
    "naver.directions": 60_000,
}

WARN_RATIO = 0.8  # 이 비율을 넘으면 경고(남은 한도로 월말까지 버틸 수 있는지 보라는 신호)
SOLD_OUT_RATIO = 1.0  # 한도 소진 — 이후 호출은 차단된다


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
        self._notified: set[tuple[str, float]] = set()  # 이미 알린 (API, 임계)

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
            self._notified.discard(name)  # 달이 바뀌면 경보도 다시 낼 수 있어야 한다
        counter.used += count
        self._maybe_notify(name, now)

    def _maybe_notify(self, name: str, now: datetime | None = None) -> None:
        """한도 임계를 처음 넘는 순간에만 알린다(매 호출 알리면 소음이다).

        /admin/metrics 를 들여다보지 않아도 요금이 시작되기 전에 눈치채야 한다.
        """
        limit = self.limit(name)
        if limit is None:
            return
        ratio = self.used(name, now) / limit
        for level in (SOLD_OUT_RATIO, WARN_RATIO):
            if ratio < level or (name, level) in self._notified:
                continue
            self._notified.add((name, level))
            text = (
                f"{name} 월 무료 한도 소진 — 이후 호출은 차단된다"
                if level >= SOLD_OUT_RATIO
                else f"{name} 월 무료 한도 {ratio * 100:.0f}% 사용"
            )
            logger.warning(text)
            _notify("quota", name, text)
            break

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
        self._notified.clear()


def _notify(kind: str, target: str, text: str) -> None:
    """알림 발송 실패가 호출 흐름을 막지 않게 한다(메트릭과 같은 원칙)."""
    from app.alerting import alert_notifier

    try:
        alert_notifier.notify(kind, target, text)
    except Exception:  # pragma: no cover - 방어적
        logger.warning("한도 알림 발송 중 예외: %s", text)


quota_store = QuotaStore()
