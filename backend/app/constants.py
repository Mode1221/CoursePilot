"""도메인 공통 상수 (여러 모듈에 흩어져 있던 매직값 통합)."""
from __future__ import annotations

from datetime import time

# 이동수단별 대략 속도 (m/분). 어댑터 근사 계산 공용.
TRAVEL_SPEED_M_PER_MIN: dict[str, int] = {"walk": 67, "car": 500, "transit": 250}

DEFAULT_REGION = "성수동"
DEFAULT_START_TIME = time(12, 0)

# 대중교통은 대기·환승·정류장 접근에 고정 비용이 든다(직선 근사에 더한다).
TRANSIT_OVERHEAD_MIN = 7
