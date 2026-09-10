#!/usr/bin/env python
"""카카오 로컬 API 스모크. 키워드 검색 1콜 + 카테고리 검색 1콜.

    python scripts/smoke_kakao.py

응답 필드가 app/adapters/kakao.py 가 읽는 이름·타입 그대로인지 대조한다.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _smoke import Smoke, run, skip  # noqa: E402

from app.config import settings  # noqa: E402


async def main() -> int:
    if not settings.kakao_rest_api_key:
        return skip("카카오 로컬", "KAKAO_REST_API_KEY 키 없음, 스킵")

    import httpx

    from app.adapters.kakao import GROUP_CODE_SLOT, to_place

    s = Smoke("카카오 로컬")
    headers = {"Authorization": f"KakaoAK {settings.kakao_rest_api_key}"}
    async with httpx.AsyncClient(timeout=10, headers=headers) as client:
        # ① 키워드 검색
        resp = await client.get(
            "https://dapi.kakao.com/v2/local/search/keyword.json",
            params={"query": "성수동 카페", "size": 5, "page": 1},
        )
        s.note(f"keyword.json HTTP {resp.status_code}")
        resp.raise_for_status()
        body = resp.json()

        s.field(body, "meta.total_count", int)
        s.field(body, "meta.is_end", bool)
        doc = s.field(body, "documents[0]", dict)
        if not isinstance(doc, dict):
            return s.done()

        # to_place() 가 읽는 필드들. x/y 는 문자열로 오고 float 로 캐스팅한다.
        s.field(doc, "id", str)
        s.field(doc, "place_name", str)
        s.field(doc, "x", str)
        s.field(doc, "y", str)
        s.field(doc, "category_name", str)
        s.field(doc, "category_group_code", str)
        s.field(doc, "road_address_name", str, required=False)
        s.field(doc, "address_name", str, required=False)

        try:
            float(doc["x"]), float(doc["y"])
            s.ok("x/y 를 float 로 변환 가능")
        except (KeyError, TypeError, ValueError) as exc:
            s.fail(f"x/y 를 float 로 못 바꿈: {exc}")

        place = to_place(doc)
        if place is None:
            s.fail("to_place() 가 None — 좌표 파싱 실패")
        else:
            s.ok(f"to_place() 정규화: {place.name} ({place.lat:.4f}, {place.lng:.4f})")

        # ② 카테고리 검색(배치가 전수 수집에 쓰는 경로)
        resp = await client.get(
            "https://dapi.kakao.com/v2/local/search/category.json",
            params={
                "category_group_code": "CE7",
                "x": doc["x"], "y": doc["y"], "radius": 1000, "size": 5, "page": 1,
            },
        )
        s.note(f"category.json HTTP {resp.status_code}")
        resp.raise_for_status()
        cat_body = resp.json()
        cat_doc = s.field(cat_body, "documents[0]", dict)
        if isinstance(cat_doc, dict):
            code = cat_doc.get("category_group_code")
            if code in GROUP_CODE_SLOT:
                s.ok(f"category_group_code={code} → 슬롯 {GROUP_CODE_SLOT[code]}")
            else:
                s.fail(f"모르는 category_group_code={code!r} (아는 코드: {sorted(GROUP_CODE_SLOT)})")

    return s.done()


if __name__ == "__main__":
    run(main)
