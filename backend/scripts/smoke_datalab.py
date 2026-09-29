#!/usr/bin/env python
"""데이터랩 검색어 트렌드 스모크 — 키·경로 확인."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx  # noqa: E402

from app.adapters import naver_datalab  # noqa: E402


async def main() -> int:
    ep = naver_datalab.endpoint()
    if ep is None:
        print("FAIL 네이버 키 없음")
        return 1
    print("endpoint:", ep[0])
    async with httpx.AsyncClient(timeout=10) as c:
        out = await naver_datalab.weekly_trends(c, ["성수 카페", "런던베이글뮤지엄"])
    if not out:
        print("FAIL 응답 없음 — NCP 콘솔에서 API HUB 앱에 '검색어트렌드'를 체크했는지 확인")
        return 1
    for k, v in out.items():
        print(f"PASS {k}: {len(v)}주, 최근 {v[-4:]}")
    return 0


raise SystemExit(asyncio.run(main()))
