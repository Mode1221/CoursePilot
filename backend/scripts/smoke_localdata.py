#!/usr/bin/env python
"""LOCALDATA CSV 스모크. 무인증 공개 파일이라 키 없이도 항상 돌린다.

    python scripts/smoke_localdata.py

이미 내려받은 CSV 가 있으면 그 파일의 컬럼을 대조하고, 없으면 각 URL 의
**앞 256KB 만 Range 로 받아** 헤더를 확인한다(전체는 200MB 대라 받지 않는다).
브라우저 User-Agent 와 Referer 가 없으면 403 이므로 실제 수집과 같은 헤더를 쓴다.

원천에 붙는 확인은 `LOCALDATA_CSV_DIR` 이 설정돼 있을 때(=실제로 수집하는 환경)
또는 `--remote` 를 줬을 때만 한다 — CI 가 외부 사이트에 의존하면 안 된다.
"""
from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _smoke import Smoke, run, skip  # noqa: E402

from app.batch.coverage import CSV_ENCODING  # noqa: E402
from app.batch.localdata_fetch import DEFAULT_CSV_URLS, headers_for  # noqa: E402
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


async def _peek(s, client, url: str) -> None:
    """앞부분만 Range 로 받아 헤더를 대조한다."""
    headers = {**headers_for(url), "Range": f"bytes=0-{HEAD_BYTES - 1}"}
    async with client.stream("GET", url, headers=headers) as resp:
        s.note(f"HTTP {resp.status_code} {resp.headers.get('content-type', '?')}")
        if resp.status_code == 403:
            s.fail("403 — User-Agent/Referer 가 막혔다(원천 정책 변경 가능)")
            return
        resp.raise_for_status()
        if "html" in (resp.headers.get("content-type") or "").lower():
            s.fail("CSV 가 아니라 HTML 이 왔다 — 차단이거나 원천 점검 중")
            return
        chunks, size = [], 0
        async for chunk in resp.aiter_bytes():
            chunks.append(chunk)
            size += len(chunk)
            if size >= HEAD_BYTES:
                break
    raw = b"".join(chunks)
    if len(raw) < 100:
        s.fail(f"응답이 너무 짧다({len(raw)}B) — 오류 페이지일 가능성")
        return
    # 응답 헤더는 charset=UTF-8 이라고 하지만 실제 본문은 CP949 다.
    text = raw.decode(CSV_ENCODING, errors="replace")
    header = next(csv.reader(io.StringIO(text)))
    s.ok(f"헤더 {len(header)}개 컬럼")
    _check_columns(s, header)


async def main() -> int:
    remote = "--remote" in sys.argv
    s = Smoke("LOCALDATA")
    directory = settings.localdata_csv_dir
    local = sorted(Path(directory).glob("*.csv")) if directory else []
    if local:
        path = local[0]
        s.note(f"내려받아 둔 파일 사용: {path.name} ({path.stat().st_size / 1e6:.1f}MB)")
        with path.open(encoding=CSV_ENCODING, errors="replace") as fh:
            header = next(csv.reader(fh))
        _check_columns(s, header)
        s.ok(f"CSV 파일 {len(local)}개 확인")
        return s.done()

    if not directory and not remote:
        return skip(
            "LOCALDATA",
            "LOCALDATA_CSV_DIR 미설정, 스킵 "
            "(원천 확인까지 하려면 --remote 또는 LOCALDATA_CSV_DIR 설정)",
        )

    urls = list(settings.localdata_csv_urls) or list(DEFAULT_CSV_URLS)

    import httpx

    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        for url in urls:
            s.note(f"앞 {HEAD_BYTES // 1024}KB 만 확인: {url}")
            await _peek(s, client, url)
    return s.done()


if __name__ == "__main__":
    run(main)
