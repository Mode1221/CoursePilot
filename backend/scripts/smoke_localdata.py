#!/usr/bin/env python
"""LOCALDATA CSV 스모크. 키가 없는 무인증 공개 파일이라 URL 설정만 본다.

    python scripts/smoke_localdata.py

이미 내려받은 CSV 가 있으면 그 파일의 컬럼을 대조하고, 없으면 첫 URL 하나만
내려받아 헤더를 확인한다(파일이 수십 MB 라 스트리밍으로 앞부분만 읽는다).
"""
from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _smoke import Smoke, run, skip  # noqa: E402

from app.config import settings  # noqa: E402

HEAD_BYTES = 256 * 1024  # 헤더 + 몇 줄이면 충분하다


def _check_columns(s, header: list[str]) -> None:
    from app.adapters.localdata import (
        _ADDR_COLS,
        _CLOSED_COLS,
        _NAME_COLS,
        _OPENED_COLS,
        _STATUS_COLS,
    )

    groups = {
        "상호": _NAME_COLS, "주소": _ADDR_COLS, "영업상태": _STATUS_COLS,
        "인허가일": _OPENED_COLS, "폐업일": _CLOSED_COLS,
    }
    for label, candidates in groups.items():
        hit = [c for c in candidates if c in header]
        if hit:
            s.ok(f"{label} 컬럼: {hit[0]}")
        else:
            s.fail(f"{label} 컬럼 없음 — 코드가 찾는 이름: {list(candidates)} / "
                   f"파일 컬럼: {header[:12]}")


async def main() -> int:
    directory = settings.localdata_csv_dir
    local = sorted(Path(directory).glob("*.csv")) if directory else []
    if not local and not settings.localdata_csv_urls:
        return skip("LOCALDATA", "LOCALDATA_CSV_URLS 미설정, 스킵 (무인증 공개 파일 URL 목록 필요)")

    s = Smoke("LOCALDATA")
    if local:
        path = local[0]
        s.note(f"내려받아 둔 파일 사용: {path.name} ({path.stat().st_size / 1e6:.1f}MB)")
        with path.open(encoding="utf-8-sig", errors="replace") as fh:
            header = next(csv.reader(fh))
        _check_columns(s, header)
        s.ok(f"CSV 파일 {len(local)}개 확인")
        return s.done()

    urls = list(settings.localdata_csv_urls)
    if not directory:
        s.fail("LOCALDATA_CSV_URLS 는 있는데 LOCALDATA_CSV_DIR 이 비었다 — 저장할 곳이 없다")
        return s.done()

    import httpx

    s.note(f"내려받은 파일이 없어 첫 URL 앞부분만 확인: {urls[0][:80]}")
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        async with client.stream("GET", urls[0]) as resp:
            s.note(f"HTTP {resp.status_code}")
            resp.raise_for_status()
            chunks, size = [], 0
            async for chunk in resp.aiter_bytes():
                chunks.append(chunk)
                size += len(chunk)
                if size >= HEAD_BYTES:
                    break
    raw = b"".join(chunks)
    if len(raw) < 100:
        s.fail(f"응답이 너무 짧다({len(raw)}B) — 오류 페이지일 가능성")
        return s.done()

    text = raw.decode("utf-8-sig", errors="replace")
    header = next(csv.reader(io.StringIO(text)))
    s.ok(f"헤더 {len(header)}개 컬럼")
    _check_columns(s, header)
    return s.done()


if __name__ == "__main__":
    run(main)
