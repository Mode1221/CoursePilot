"""인메모리 요청 메트릭 (관측성). 외부 APM 없이 엔드포인트별 상태를 확인한다.

라우트 템플릿(`/courses/{course_id}`) 단위로 집계하므로 카디널리티가 폭발하지 않는다.
단일 프로세스 기준이며, 다중 인스턴스에서는 인스턴스별 값이다.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field

SAMPLE_SIZE = 200  # 라우트별 보관하는 최근 지연시간 샘플 수


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


class MetricsStore:
    def __init__(self) -> None:
        self._routes: dict[str, RouteStat] = defaultdict(RouteStat)

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
        return {
            "total_requests": total,
            "error_rate": round(errors / total, 4) if total else 0.0,
            "routes": routes,
        }

    def clear(self) -> None:
        self._routes.clear()


metrics_store = MetricsStore()
