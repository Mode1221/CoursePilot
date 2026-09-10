#!/usr/bin/env python
"""네이버 스모크. 지역검색 1콜 + (NCP 키가 있으면) 차량 경로 1콜.

    python scripts/smoke_naver.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _smoke import Smoke, run, skip  # noqa: E402

from app.config import settings  # noqa: E402


async def main() -> int:
    if not (settings.naver_client_id and settings.naver_client_secret):
        return skip("네이버", "NAVER_CLIENT_ID/SECRET 키 없음, 스킵")

    import httpx

    from app.adapters.naver import _directions_headers, _katech_to_wgs84, _route_summary

    s = Smoke("네이버")
    headers = {
        "X-Naver-Client-Id": settings.naver_client_id,
        "X-Naver-Client-Secret": settings.naver_client_secret,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        # ① 지역 검색
        resp = await client.get(
            "https://openapi.naver.com/v1/search/local.json",
            params={"query": "성수동 카페", "display": 5},
            headers=headers,
        )
        s.note(f"search/local.json HTTP {resp.status_code}")
        resp.raise_for_status()
        body = resp.json()

        s.field(body, "total", int)
        item = s.field(body, "items[0]", dict)
        if not isinstance(item, dict):
            return s.done()

        s.field(item, "title", str)
        s.field(item, "category", str, required=False)
        s.field(item, "roadAddress", str, required=False)
        s.field(item, "address", str, required=False)
        # mapx/mapy 는 KATECH 문자열(*1e7). 숫자로 오면 변환 가정이 깨진다.
        s.field(item, "mapx", str)
        s.field(item, "mapy", str)

        coords = _katech_to_wgs84(item.get("mapx"), item.get("mapy"))
        if coords is None:
            s.fail(f"좌표 변환 실패 — mapx={item.get('mapx')!r} mapy={item.get('mapy')!r} "
                   "(한국 범위 밖이거나 표기 방식이 바뀌었다)")
        else:
            s.ok(f"KATECH→WGS84 변환: {coords[0]:.4f}, {coords[1]:.4f}")

        # ② 차량 경로(NCP). 키가 없으면 개발자센터 키로 폴백하지만 보통 401 이다.
        if not (settings.ncp_api_key_id and settings.ncp_api_key):
            s.note("NCP_API_KEY_ID/KEY 없음 — 경로 API 는 건너뛴다(직선거리 근사로 동작)")
            return s.done()

        resp = await client.get(
            "https://maps.apigw.ntruss.com/map-direction/v1/driving",
            params={"start": "127.0557,37.5445", "goal": "127.0286,37.5273"},
            headers=_directions_headers(),
        )
        s.note(f"map-direction HTTP {resp.status_code}")
        if resp.status_code == 401:
            s.fail("경로 API 401 — NCP 키가 아니거나 Directions 5 이용 신청이 안 된 상태")
            return s.done()
        resp.raise_for_status()
        route_body = resp.json()
        s.field(route_body, "code", int)
        summary = _route_summary(route_body)
        if summary is None:
            s.fail(f"route 요약을 못 찾음 — 최상위 키: {sorted(route_body)} "
                   f"(코드가 보는 경로: route.traoptimal[0].summary)")
        else:
            s.ok(f"route 요약 확인 (code={route_body.get('code')})")
            s.field(summary, "duration", int)  # ms
            s.field(summary, "distance", int)  # m

    return s.done()


if __name__ == "__main__":
    run(main)
