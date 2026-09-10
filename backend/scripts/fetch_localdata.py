#!/usr/bin/env python
"""LOCALDATA CSV 내려받기(주 1회).

    python scripts/fetch_localdata.py
    python scripts/fetch_localdata.py --url <csv-url> --url <csv-url>

URL 을 주지 않으면 LOCALDATA_CSV_URLS 설정을 쓴다. 저장 위치는 LOCALDATA_CSV_DIR.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.batch.coverage import covered_sigungu, missing_districts  # noqa: E402
from app.batch.db_setup import connect_db  # noqa: E402
from app.batch.localdata_fetch import fetch_all  # noqa: E402
from app.config import settings  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="LOCALDATA CSV 내려받기")
    ap.add_argument("--url", action="append", help="CSV URL(여러 번 지정 가능)")
    ap.add_argument("--dir", help="저장 디렉터리(기본: LOCALDATA_CSV_DIR)")
    ap.add_argument(
        "--check-only",
        action="store_true",
        help="내려받지 않고, 이미 있는 파일이 24개 상권의 시군구를 덮는지만 확인",
    )
    args = ap.parse_args()
    connect_db()  # 배치는 앱과 별개 프로세스라 DB 를 직접 열어야 한다

    target = args.dir or settings.localdata_csv_dir
    if not target:
        print("LOCALDATA_CSV_DIR 을 설정하거나 --dir 을 지정하라.", file=sys.stderr)
        return 1
    if not args.check_only:
        report = asyncio.run(fetch_all(args.url, target))
        print(f"저장 {len(report.saved)} / 실패 {len(report.failed)} → {target}")
        for url in report.failed:
            print(f"  실패: {url}", file=sys.stderr)
        if report.failed and not report.saved:
            return 1

    # 파일이 있어도 상권의 시군구를 못 덮으면 그 상권은 폐업 판정이 통째로 빠진다
    covered = covered_sigungu(target)
    missing = missing_districts(target)
    print(f"시군구 커버리지: {len(covered)}/{len(covered) + len(missing)}")
    for sigungu, files in sorted(covered.items()):
        extra = f" 외 {len(files) - 1}개" if len(files) > 1 else ""
        print(f"  ✓ {sigungu}: {files[0]}{extra}")
    if missing:
        print("\n다음 시군구 CSV 가 없어 폐업 판정이 빠진다:", file=sys.stderr)
        for sigungu, districts in sorted(missing.items()):
            print(f"  ✗ {sigungu} — 영향 상권: {', '.join(districts)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
