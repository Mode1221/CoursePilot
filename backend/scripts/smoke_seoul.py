#!/usr/bin/env python
"""서울 열린데이터광장 스모크 — 실시간 도시데이터(상권별 장소명 검증)와 문화행사."""
import asyncio
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx  # noqa: E402

from app.adapters import seoul_openapi as so  # noqa: E402
from app.config import settings  # noqa: E402


async def main() -> int:
    if not settings.seoul_openapi_key:
        print("FAIL SEOUL_OPENAPI_KEY 없음")
        return 1
    bad = 0
    async with httpx.AsyncClient(timeout=10) as c:
        for region, area in so.CITYDATA_AREA.items():
            st = await so.area_status(c, region)
            if st and st.level:
                print(f"PASS {region:<6} → {st.area:<14} {st.level:<6} 한산:{st.calmer_hour or '-'}  행사 {len(st.events)}")
            else:
                bad += 1
                print(f"FAIL {region:<6} → {area} (장소명이 공식 목록과 다를 수 있음)")
        ev = await so.cultural_events(c, date.today())
    print(f"문화행사(오늘 진행 중, 서울 좌표): {len(ev)}건")
    for e in ev[:5]:
        print(f"  {e['kind']} | {e['name']} | {e['place']} | ~{e['end']}")
    return 1 if bad == len(so.CITYDATA_AREA) else 0


raise SystemExit(asyncio.run(main()))
