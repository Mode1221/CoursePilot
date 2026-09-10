"""LOCALDATA 파일이 우리 상권을 다 덮는지 확인.

LOCALDATA 는 시군구 단위 파일로 배포된다. 어떤 시군구 파일을 빠뜨리면 그 상권은
폐업 판정이 통째로 빠진 채 수집된다 — 조용히 문 닫은 가게가 코스에 섞인다.
그래서 "내려받은 파일들이 24개 상권의 시군구를 다 덮는가"를 먼저 본다.
"""
from __future__ import annotations

import csv
from pathlib import Path

from app.batch.districts import DISTRICTS

SAMPLE_ROWS = 300  # 파일 앞부분만 봐도 어느 시군구인지 판별된다(수십 MB 전체를 읽지 않는다)
_ADDR_COLS = ("도로명전체주소", "소재지전체주소", "도로명주소", "소재지주소")


def required_sigungu() -> dict[str, list[str]]:
    """시군구 → 그 시군구에 속한 상권 이름들."""
    out: dict[str, list[str]] = {}
    for district in DISTRICTS:
        if district.sigungu:
            out.setdefault(district.sigungu, []).append(district.name)
    return out


def sigungu_in_file(path: Path, sample_rows: int = SAMPLE_ROWS) -> set[str]:
    """CSV 앞부분의 주소에서 등장하는 시군구 이름을 모은다."""
    wanted = set(required_sigungu())
    found: set[str] = set()
    try:
        with path.open(encoding="utf-8-sig", errors="replace", newline="") as fh:
            reader = csv.DictReader(fh)
            columns = [c for c in _ADDR_COLS if c in (reader.fieldnames or [])]
            if not columns:
                return found
            for index, row in enumerate(reader):
                if index >= sample_rows:
                    break
                address = next((row.get(c) or "" for c in columns if row.get(c)), "")
                for name in wanted:
                    if name in address:
                        found.add(name)
    except OSError:
        return found
    return found


def covered_sigungu(directory: str | Path) -> dict[str, list[str]]:
    """디렉터리의 CSV 들이 덮는 시군구 → 그것을 담은 파일 이름들."""
    path = Path(directory)
    out: dict[str, list[str]] = {}
    if not path.is_dir():
        return out
    for csv_path in sorted(path.glob("*.csv")):
        for name in sigungu_in_file(csv_path):
            out.setdefault(name, []).append(csv_path.name)
    return out


def missing_districts(directory: str | Path) -> dict[str, list[str]]:
    """폐업 판정이 빠지는 시군구 → 영향받는 상권들."""
    covered = set(covered_sigungu(directory))
    return {
        sigungu: districts
        for sigungu, districts in required_sigungu().items()
        if sigungu not in covered
    }
