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

from app.batch.localdata_fetch import fetch_all  # noqa: E402
from app.config import settings  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="LOCALDATA CSV 내려받기")
    ap.add_argument("--url", action="append", help="CSV URL(여러 번 지정 가능)")
    ap.add_argument("--dir", help="저장 디렉터리(기본: LOCALDATA_CSV_DIR)")
    args = ap.parse_args()

    target = args.dir or settings.localdata_csv_dir
    if not target:
        print("LOCALDATA_CSV_DIR 을 설정하거나 --dir 을 지정하라.", file=sys.stderr)
        return 1
    report = asyncio.run(fetch_all(args.url, target))
    print(f"저장 {len(report.saved)} / 실패 {len(report.failed)} → {target}")
    for url in report.failed:
        print(f"  실패: {url}", file=sys.stderr)
    return 0 if report.saved or not report.failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
