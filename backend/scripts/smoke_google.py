#!/usr/bin/env python
"""Google Places 스모크. 유료 API 라 quota.py 를 거쳐 최소 콜만 쓴다.

    python scripts/smoke_google.py

콜 3건(IDs-only 1 + Pro 1 + Enterprise 1). 티어를 섞지 않는 전제도 함께 확인한다.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _smoke import Smoke, run, skip  # noqa: E402

from app.config import settings  # noqa: E402


async def main() -> int:
    if not settings.google_maps_api_key:
        return skip("Google Places", "GOOGLE_MAPS_API_KEY 키 없음, 스킵")

    from app.adapters.google import (
        DETAILS_MASK,
        IDS_ONLY_MASK,
        GooglePlacesClient,
        has_periods,
    )
    from app.quota import quota_store
    from app.schemas import Place

    s = Smoke("Google Places")

    # Text Search(IDs-only)와 Place Details(Enterprise)는 SKU 가 다르다 — 섞이면
    # IDs-only 콜이 Enterprise 로 청구된다. Details 안의 필드는 같은 SKU 라 한 콜로 받는다.
    mixed = [f for f in ("rating", "Hours", "businessStatus") if f in IDS_ONLY_MASK]
    if mixed:
        s.fail(f"IDs-only 마스크에 Details 필드가 섞임: {mixed} — 과금 SKU 가 올라간다")
    else:
        s.ok(f"IDs-only 필드마스크 유지: {IDS_ONLY_MASK}")
    s.ok(f"Details(Enterprise) 필드마스크: {DETAILS_MASK}")

    client = GooglePlacesClient()
    probe = Place(
        id="smoke", name="서울숲", category="공원",
        address="서울 성동구 뚝섬로 273", lat=37.5445, lng=127.0374,
    )

    before = {k: quota_store.used(k) for k in ("google.map_id", "google.details")}

    # ① 매핑(IDs-only)
    place_id = await client.map_place_id(probe)
    if not place_id:
        s.fail("place_id 매핑 실패 — 키 제한(IP)·Places API(New) 활성화·무료 한도를 확인")
        return s.done()
    s.ok(f"place_id 매핑: {place_id}")

    # ② 상세(Enterprise): 영업시간 + 평점 + 영업상태를 한 콜로
    hours = await client.fetch_details(place_id)
    if hours is None:
        s.fail("상세 응답 없음 — 무료 한도 소진이거나 Enterprise SKU 미허용")
    else:
        s.field(hours, "businessStatus", str, required=False)
        if has_periods(hours.get("regularOpeningHours")):
            s.ok("regularOpeningHours.periods 존재")
            s.field(hours, "regularOpeningHours.periods[0].open.day", int)
            s.field(hours, "regularOpeningHours.periods[0].open.hour", int)
            s.field(hours, "regularOpeningHours.periods[0].open.minute", int, required=False)
        else:
            s.note(f"이 장소엔 periods 가 없다(24시간 영업 등). 최상위 키: {sorted(hours)}")

    # ③ 평점은 같은 응답에서 꺼낸다(추가 콜 없음)
    rating = client.rating_of(hours or {})
    if rating is None:
        s.note("평점 없음 — 평가 수가 기준 미만(정상 폴백)")
    else:
        value, count = rating
        s.ok(f"평점 {value} / 평가 {count:,}건 (추가 콜 없이 같은 응답에서)")

    # 유료 콜이 quota 에 실제로 기록됐는지(대시보드·한도 차단이 여기에 의존한다)
    for key, was in before.items():
        now = quota_store.used(key)
        if now > was:
            s.ok(f"quota 기록됨: {key} {was} → {now}")
        else:
            s.fail(f"quota 미기록: {key} 가 {was} 그대로 — 무료 한도 차단이 동작하지 않는다")

    return s.done()


if __name__ == "__main__":
    run(main)
