#!/usr/bin/env python
"""저장된 장소의 주기 갱신(폐업 주 1회 / 영업시간 30일 / 평점 90일).

    python scripts/refresh_places.py                  # 하루 치 할당량만큼
    python scripts/refresh_places.py --hours-limit 0  # 폐업 필터만

크론 예: 매일 04:00 실행. 폐업 대장(LOCALDATA CSV)은 주 1회만 다시 읽는다.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.batch.places_build import HOURS_PER_DAY, RATINGS_PER_DAY  # noqa: E402
from app.batch.refresh import run  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="장소 주기 갱신")
    ap.add_argument("--hours-limit", type=int, default=HOURS_PER_DAY)
    ap.add_argument("--ratings-limit", type=int, default=RATINGS_PER_DAY)
    args = ap.parse_args()

    report = asyncio.run(
        run(hours_limit=args.hours_limit, ratings_limit=args.ratings_limit)
    )
    print(f"스캔 {report.scanned} / 활성 {report.active}")
    print(f"폐업 제거 {report.closed_removed} / 업력 갱신 {report.longevity_filled}")
    print(f"영업시간 {report.hours_filled} / 평점 {report.ratings_filled}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
