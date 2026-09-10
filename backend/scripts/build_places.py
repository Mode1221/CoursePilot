#!/usr/bin/env python
"""상권 장소 DB 구축 배치(하루 1회 실행 전제).

    python scripts/build_places.py                 # 전체 상권
    python scripts/build_places.py --district 성수 연남
    python scripts/build_places.py --hours-limit 0 # 수집·폐업 필터만

Google 콜은 무료 한도 안에서 페이싱되므로, 여러 날에 걸쳐 조금씩 채워진다.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.batch.db_setup import connect_db  # noqa: E402
from app.batch.districts import DISTRICTS  # noqa: E402
from app.batch.lock import LockBusy, batch_lock  # noqa: E402
from app.batch.places_build import HOURS_PER_DAY, RATINGS_PER_DAY, run  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="상권 장소 수집·보강 배치")
    ap.add_argument("--district", nargs="*", help="상권 이름(기본: 전체)")
    ap.add_argument("--hours-limit", type=int, default=HOURS_PER_DAY)
    ap.add_argument("--ratings-limit", type=int, default=RATINGS_PER_DAY)
    ap.add_argument(
        "--sample",
        action="store_true",
        help="키 없이 합성 데이터로 리허설(스키마·용량·페이싱 확인용, 운영 금지)",
    )
    args = ap.parse_args()
    connect_db()  # 배치는 앱과 별개 프로세스라 DB 를 직접 열어야 한다

    targets = DISTRICTS
    if args.district:
        names = set(args.district)
        targets = tuple(d for d in DISTRICTS if d.name in names)
        if not targets:
            print(f"알 수 없는 상권: {', '.join(sorted(names))}", file=sys.stderr)
            return 1

    kakao = None
    if args.sample:
        from app.batch.sample_source import SamplePlaceSource

        kakao = SamplePlaceSource()
        print("※ 합성 데이터 리허설 모드 — 실제 장소가 아닙니다", file=sys.stderr)
    try:
        with batch_lock("places_build"):
            report = asyncio.run(
                run(
                    targets,
                    hours_limit=args.hours_limit,
                    ratings_limit=args.ratings_limit,
                    kakao=kakao,
                )
            )
    except LockBusy as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"상권 {len(report.districts)}곳: {', '.join(report.districts)}")
    print(f"수집 {report.collected} / 폐업 제거 {report.closed_removed}")
    print(
        f"영업시간 {report.hours_filled} / 평점 {report.ratings_filled} / "
        f"인지도 {report.awareness_filled} / 저장 {report.upserted}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
