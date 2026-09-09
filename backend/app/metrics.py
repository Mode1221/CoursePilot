"""인메모리 요청 메트릭 (관측성). 외부 APM 없이 엔드포인트별 상태를 확인한다.

라우트 템플릿(`/courses/{course_id}`) 단위로 집계하므로 카디널리티가 폭발하지 않는다.
단일 프로세스 기준이며, 다중 인스턴스에서는 인스턴스별 값이다.
"""
from __future__ import annotations

import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field

logger = logging.getLogger("coursepilot")

SAMPLE_SIZE = 200  # 라우트별 보관하는 최근 지연시간 샘플 수

# 경고 임계값: 표본이 이 정도는 쌓여야 비율을 신뢰한다
MIN_ALERT_SAMPLES = 10
FALLBACK_RATE_ALERT = 0.5  # 외부 연동 절반 이상이 폴백이면 키·엔드포인트 점검 필요
ERROR_RATE_ALERT = 0.05  # 5xx 비율


@dataclass
class RouteStat:
    count: int = 0
    errors: int = 0  # 5xx
    client_errors: int = 0  # 4xx
    latencies_ms: deque[float] = field(default_factory=lambda: deque(maxlen=SAMPLE_SIZE))


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round((pct / 100) * (len(ordered) - 1))))
    return round(ordered[idx], 1)


@dataclass
class ExternalStat:
    """외부 어댑터 호출 결과. 폴백 비율이 곧 외부 연동 건강도다."""

    ok: int = 0
    fallback: int = 0


class MetricsStore:
    def __init__(self) -> None:
        self._routes: dict[str, RouteStat] = defaultdict(RouteStat)
        self._externals: dict[str, ExternalStat] = defaultdict(ExternalStat)
        self._alerting: set[str] = set()  # 이미 경고를 남긴 항목(로그 폭주 방지)

    def record_external(self, name: str, ok: bool) -> None:
        """외부 호출 1건 기록. ok=False 면 폴백으로 처리된 호출.

        임계(폴백률)를 넘거나 회복되는 순간에만 로그를 남긴다 —
        /admin/metrics 를 들여다보지 않아도 눈에 띄게 하기 위함.
        """
        stat = self._externals[name]
        if ok:
            stat.ok += 1
        else:
            stat.fallback += 1
        self._log_transition(name, stat)

    def _log_transition(self, name: str, stat: ExternalStat) -> None:
        samples = stat.ok + stat.fallback
        if samples < MIN_ALERT_SAMPLES:
            return
        rate = stat.fallback / samples
        if rate >= FALLBACK_RATE_ALERT and name not in self._alerting:
            self._alerting.add(name)
            logger.warning("외부 연동 폴백률 %.0f%% — %s (표본 %d)", rate * 100, name, samples)
            _notify(
                "fallback_rate",
                name,
                f"외부 연동 폴백률 {rate * 100:.0f}% — {name} (표본 {samples})",
            )
        elif rate < FALLBACK_RATE_ALERT and name in self._alerting:
            self._alerting.discard(name)
            logger.info("외부 연동 폴백률 회복 — %s (%.0f%%)", name, rate * 100)
            _notify("fallback_recovered", name, f"외부 연동 폴백률 회복 — {name}")

    def record(self, key: str, status: int, elapsed_ms: float) -> None:
        stat = self._routes[key]
        stat.count += 1
        if status >= 500:
            stat.errors += 1
        elif status >= 400:
            stat.client_errors += 1
        stat.latencies_ms.append(elapsed_ms)

    def snapshot(self) -> dict:
        """엔드포인트별 요약. 요청 수 내림차순."""
        routes = []
        for key, stat in self._routes.items():
            samples = list(stat.latencies_ms)
            routes.append(
                {
                    "route": key,
                    "count": stat.count,
                    "errors": stat.errors,
                    "client_errors": stat.client_errors,
                    "p50_ms": _percentile(samples, 50),
                    "p95_ms": _percentile(samples, 95),
                }
            )
        routes.sort(key=lambda r: -r["count"])
        total = sum(r["count"] for r in routes)
        errors = sum(r["errors"] for r in routes)
        externals = [
            {
                "name": name,
                "ok": stat.ok,
                "fallback": stat.fallback,
                "fallback_rate": (
                    round(stat.fallback / (stat.ok + stat.fallback), 4)
                    if (stat.ok + stat.fallback)
                    else 0.0
                ),
            }
            for name, stat in sorted(self._externals.items())
        ]
        error_rate = round(errors / total, 4) if total else 0.0
        from app.quota import quota_store

        quota_rows = quota_store.snapshot()
        quota_alerts = quota_store.alerts()
        return {
            "total_requests": total,
            "error_rate": error_rate,
            "routes": routes,
            "externals": externals,
            "quotas": quota_rows,
            "alerts": _alerts(total, error_rate, externals) + quota_alerts,
        }

    def clear(self) -> None:
        self._routes.clear()
        self._externals.clear()
        self._alerting.clear()


def _alerts(total: int, error_rate: float, externals: list[dict]) -> list[dict]:
    """임계 초과 항목을 그대로 알림 목록으로 돌려준다(운영자 확인용)."""
    alerts: list[dict] = []
    if total >= MIN_ALERT_SAMPLES and error_rate >= ERROR_RATE_ALERT:
        alerts.append({"kind": "error_rate", "target": "all", "value": error_rate})
    for ext in externals:
        samples = ext["ok"] + ext["fallback"]
        if samples >= MIN_ALERT_SAMPLES and ext["fallback_rate"] >= FALLBACK_RATE_ALERT:
            alerts.append(
                {"kind": "fallback_rate", "target": ext["name"], "value": ext["fallback_rate"]}
            )
    return alerts


def _notify(kind: str, target: str, text: str) -> None:
    """알림 발송은 실패해도 메트릭 기록을 막지 않는다."""
    from app.alerting import alert_notifier

    try:
        alert_notifier.notify(kind, target, text)
    except Exception:  # pragma: no cover - 방어적
        logger.warning("알림 발송 중 예외: %s", text)


metrics_store = MetricsStore()
