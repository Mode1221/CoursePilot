#!/usr/bin/env python
"""LOCALDATA 영업상태 값 분포를 찍어 본다(폐업 판정 기준 근거).

    python scripts/localdata_status_dist.py [--dir DIR] [--rows N]

폐업 판정은 "폐업일자 → 상세영업상태명 → 영업상태명" 순이다. 어떤 값이 실제로
얼마나 나오는지 확인해 `app/adapters/localdata.py` 의 _CLOSED_STATUSES 를 검증한다.
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.adapters.localdata import _CLOSED_STATUSES  # noqa: E402
from app.batch.coverage import CSV_ENCODING  # noqa: E402
from app.config import settings  # noqa: E402

COLUMNS = ("영업상태명", "상세영업상태명")


def scan(path: Path, rows: int) -> tuple[dict[str, Counter], int, int]:
    counters = {col: Counter() for col in COLUMNS}
    total = closed_dates = 0
    with path.open(encoding=CSV_ENCODING, errors="replace", newline="") as fh:
        for index, row in enumerate(csv.DictReader(fh)):
            if index >= rows:
                break
            total += 1
            if (row.get("폐업일자") or "").strip():
                closed_dates += 1
            for col in COLUMNS:
                counters[col][(row.get(col) or "").strip() or "(빈값)"] += 1
    return counters, total, closed_dates


def main() -> int:
    ap = argparse.ArgumentParser(description="LOCALDATA 영업상태 분포")
    ap.add_argument("--dir", help="CSV 디렉터리(기본: LOCALDATA_CSV_DIR)")
    ap.add_argument("--rows", type=int, default=200_000, help="파일당 읽을 행 수")
    args = ap.parse_args()

    directory = args.dir or settings.localdata_csv_dir
    if not directory:
        print("LOCALDATA_CSV_DIR 을 설정하거나 --dir 을 지정하라.", file=sys.stderr)
        return 1
    files = sorted(Path(directory).glob("*.csv"))
    if not files:
        print(f"CSV 가 없다: {directory}", file=sys.stderr)
        return 1

    for path in files:
        counters, total, closed_dates = scan(path, args.rows)
        print(f"\n== {path.name} (표본 {total:,}행) ==")
        print(f"폐업일자 채워진 행: {closed_dates:,} ({closed_dates / max(total, 1):.1%})")
        for col in COLUMNS:
            print(f"  [{col}]")
            for value, count in counters[col].most_common(15):
                mark = "폐업" if any(w in value for w in _CLOSED_STATUSES) else "영업"
                print(f"    {mark}  {value:<20} {count:>9,} ({count / max(total, 1):.1%})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
