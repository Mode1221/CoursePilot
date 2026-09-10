#!/usr/bin/env python
"""KOPIS(공연예술통합전산망) 스모크. 공연 목록 1콜.

    python scripts/smoke_kopis.py

KOPIS 는 XML 로만 응답한다 — 파서가 기대하는 태그가 그대로인지 본다.
키는 TOURAPI_SERVICE_KEY 를 공유한다(공공데이터포털 공통 키).
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _smoke import Smoke, run, skip  # noqa: E402

from app.config import settings  # noqa: E402


async def main() -> int:
    if not settings.tourapi_service_key:
        return skip("KOPIS", "TOURAPI_SERVICE_KEY 키 없음, 스킵")

    from app.adapters.culture import CultureClient, _xml_items, to_performance

    s = Smoke("KOPIS")
    client = CultureClient()
    today = date.today()

    resp = await client._client.get(
        "http://kopis.or.kr/openApi/restful/pblprfr",
        params={
            "service": settings.tourapi_service_key,
            "stdate": today.strftime("%Y%m%d"),
            "eddate": today.strftime("%Y%m%d"),
            "cpage": 1, "rows": 5, "signgucode": "11",
        },
    )
    s.note(f"pblprfr HTTP {resp.status_code}")
    resp.raise_for_status()

    text = resp.text
    if "<dbs>" not in text and "<db>" not in text:
        s.fail("XML <db> 항목이 없음 — KOPIS 는 공공데이터포털과 별도 키를 쓴다. "
               f"응답 앞부분: {text[:200]!r}")
        return s.done()

    items = _xml_items(text)
    if not items:
        s.fail("_xml_items() 가 0건 — 태그 구조가 바뀌었거나 오늘 공연이 없다")
        return s.done()
    s.ok(f"_xml_items() 로 {len(items)}건 파싱")

    item = items[0]
    for tag in ("mt20id", "prfnm", "fcltynm", "prfpdfrom", "prfpdto"):
        if tag in item:
            s.ok(f"<{tag}> = {str(item[tag])[:40]}")
        else:
            s.fail(f"<{tag}> 없음 — 실제 태그: {sorted(item)[:15]}")

    performance = to_performance(item)
    if performance is None:
        s.fail(f"to_performance() 가 None — 기간 파싱 실패 "
               f"(prfpdfrom={item.get('prfpdfrom')!r} prfpdto={item.get('prfpdto')!r})")
    else:
        s.ok(f"정규화: {performance.title} @ {performance.venue} "
             f"({performance.start}~{performance.end})")
        if performance.runs_on(today):
            s.ok("오늘 진행 중으로 판정")
        else:
            s.fail(f"오늘({today}) 조회인데 진행 중이 아님 — 기간 해석이 어긋났다")

    return s.done()


if __name__ == "__main__":
    run(main)
