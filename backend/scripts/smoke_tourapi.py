#!/usr/bin/env python
"""TourAPI(공공데이터포털) 스모크. 키워드 검색 1콜 + 소개정보 1콜.

    python scripts/smoke_tourapi.py

공공데이터포털은 키 인코딩(Encoding/Decoding) 실수가 잦아 실패 사유를 함께 찍는다.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _smoke import Smoke, run, skip  # noqa: E402

from app.config import settings  # noqa: E402


async def main() -> int:
    if not settings.tourapi_service_key:
        return skip("TourAPI", "TOURAPI_SERVICE_KEY 키 없음, 스킵")

    from app.adapters.tourapi import (
        CONTENT_TYPE_INTRO_FIELDS,
        TourApiClient,
        _items,
        parse_hours,
    )

    s = Smoke("TourAPI")
    client = TourApiClient()

    # ① 키워드 검색
    resp = await client._client.get(
        "https://apis.data.go.kr/B551011/KorService2/searchKeyword2",
        params=client._params(keyword="서울숲", numOfRows=1, pageNo=1),
    )
    s.note(f"searchKeyword2 HTTP {resp.status_code}")
    resp.raise_for_status()
    if not resp.text.lstrip().startswith("{"):
        s.fail("JSON 이 아닌 응답 — 보통 키가 잘못됐거나(SERVICE_KEY_IS_NOT_REGISTERED) "
               f"인코딩된 키를 그대로 넣은 경우다. 앞부분: {resp.text[:200]!r}")
        return s.done()

    body = resp.json()
    header_code = body.get("response", {}).get("header", {}).get("resultCode")
    if header_code not in ("0000", "00", None):
        msg = body.get("response", {}).get("header", {}).get("resultMsg")
        s.fail(f"resultCode={header_code!r} ({msg!r}) — 활용신청 승인·키 종류를 확인")
        return s.done()
    s.ok(f"resultCode={header_code!r}")

    items = _items(body)
    if not items:
        s.fail(f"items 가 비었음 — 코드가 보는 경로: response.body.items.item, "
               f"실제 body 키: {sorted(body.get('response', {}).get('body', {}))}")
        return s.done()
    item = items[0]
    s.ok(f"_items() 로 {len(items)}건 정규화 (단건 dict/다건 list 모두 처리)")

    s.field(item, "contentid", (str, int))
    s.field(item, "contenttypeid", (str, int))
    s.field(item, "title", str)

    content_type = str(item.get("contenttypeid"))
    if content_type not in CONTENT_TYPE_INTRO_FIELDS:
        s.note(f"contenttypeid={content_type} 는 소개정보 필드 매핑이 없다 "
               f"(아는 타입: {sorted(CONTENT_TYPE_INTRO_FIELDS)})")
        return s.done()

    # ② 소개정보(이용시간)
    intro = await client.intro(str(item["contentid"]), content_type)
    if intro is None:
        s.fail("detailIntro2 응답이 비었음")
        return s.done()
    time_field, rest_field = CONTENT_TYPE_INTRO_FIELDS[content_type]
    if time_field in intro:
        raw = intro.get(time_field)
        s.ok(f"{time_field} = {str(raw)[:60]!r}")
        parsed = parse_hours(raw)
        if parsed:
            s.ok(f"이용시간 파싱: {parsed[0]}~{parsed[1]}")
        else:
            s.note("자유서술이라 시각을 못 뽑음(정상 — 영업시간 미확인으로 표시된다)")
    else:
        s.fail(f"{time_field} 필드 없음 — 응답 키: {sorted(intro)[:15]}")
    s.field(intro, rest_field, str, required=False)

    return s.done()


if __name__ == "__main__":
    run(main)
