"""LOCALDATA 파일이 우리 상권을 다 덮는지 확인.

신원천(file.localdata.go.kr)은 **업종 단위 전국 파일**로 배포된다(구원천은 시군구
단위였다). 전국 파일이라도 특정 시군구 행이 실제로 들어 있는지는 봐야 한다 —
어떤 시군구가 빠지면 그 상권은 폐업 판정이 통째로 빠진 채 수집된다.

파일이 200MB 대라 통째로 메모리에 올리지 않고 한 줄씩 흘리며 읽고, 24개 상권의
시군구를 전부 찾으면 즉시 멈춘다(앞부분만 보면 자치단체코드 순으로 정렬돼 있어
서울 일부만 잡힌다).
"""
from __future__ import annotations

import csv
from pathlib import Path

from app.batch.districts import DISTRICTS

# LOCALDATA CSV 는 CP949 다(응답 헤더는 charset=UTF-8 이라고 하지만 본문은 CP949).
CSV_ENCODING = "cp949"
MAX_ROWS = 4_000_000  # 전국 파일 전체를 훑되 무한 루프는 막는다
_ADDR_COLS = ("도로명전체주소", "소재지전체주소", "도로명주소", "소재지주소", "지번주소")


def required_sigungu() -> dict[str, list[str]]:
    """시군구 → 그 시군구에 속한 상권 이름들."""
    out: dict[str, list[str]] = {}
    for district in DISTRICTS:
        if district.sigungu:
            out.setdefault(district.sigungu, []).append(district.name)
    return out


def sigungu_in_file(path: Path, max_rows: int = MAX_ROWS) -> set[str]:
    """CSV 주소 칼럼에 등장하는 시군구 이름을 모은다(다 찾으면 조기 종료)."""
    wanted = set(required_sigungu())
    found: set[str] = set()
    try:
        with path.open(encoding=CSV_ENCODING, errors="replace", newline="") as fh:
            reader = csv.DictReader(fh)
            columns = [c for c in _ADDR_COLS if c in (reader.fieldnames or [])]
            if not columns:
                return found
            for index, row in enumerate(reader):
                if index >= max_rows or found == wanted:
                    break
                address = next((row.get(c) or "" for c in columns if row.get(c)), "")
                for name in wanted - found:
                    if name in address:
                        found.add(name)
    except (OSError, csv.Error):
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
