#!/usr/bin/env python
"""구축 결과 점검 — 배치를 돌린 뒤 "제대로 쌓였는가"를 한 번에 본다.

    python scripts/verify_places.py

상권별 건수 / 슬롯 미매핑 / 폐업 제거율 / Google 매핑 비율 / 영업시간·평점 채움률.
DB 가 붙어 있어야 한다(없으면 인메모리라 볼 것이 없다).
"""
from __future__ import annotations

import logging
import sys
from collections import Counter
from math import atan2, cos, radians, sin, sqrt
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.adapters.kakao import slot_for  # noqa: E402
from app.batch.db_setup import connect_db  # noqa: E402
from app.batch.districts import DISTRICTS  # noqa: E402
from app.batch.localdata_boot import load_localdata_or_exit  # noqa: E402
from app.pipeline.planner import classify  # noqa: E402

MIN_PER_DISTRICT = 300  # 이보다 적으면 수집이 카카오 질의 상한에 걸린 것이다

BAR = "█"
LIMIT = 100_000  # 스냅샷 상한(상권 24곳 규모에서는 충분)


def _distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6_371_000
    p1, p2 = radians(lat1), radians(lat2)
    dp, dl = radians(lat2 - lat1), radians(lng2 - lng1)
    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * r * atan2(sqrt(a), sqrt(1 - a))


def _nearest_district(lat: float, lng: float) -> str:
    """좌표로 상권을 되짚는다(장소에 상권 표시를 따로 저장하지 않는다)."""
    best, best_d = "(범위 밖)", float("inf")
    for district in DISTRICTS:
        d = _distance_m(lat, lng, district.lat, district.lng)
        if d < best_d:
            best, best_d = district.name, d
    return best if best_d <= 5000 else "(범위 밖)"


def _pct(part: int, whole: int) -> str:
    if not whole:
        return "  -  "
    return f"{part / whole * 100:5.1f}%"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not connect_db():
        print("DB 에 연결하지 못했습니다 — 확인할 대상이 없습니다.", file=sys.stderr)
        return 1

    from app.places import place_repo

    places = place_repo.all(limit=LIMIT)
    total = len(places)
    if not total:
        print("저장된 장소가 없습니다. 먼저 scripts/build_places.py 를 돌리세요.")
        return 1

    print(f"\n총 {total:,}건\n")

    # ① 상권별 건수
    print("── 상권별 건수 " + "─" * 40)
    per_district = Counter(_nearest_district(p.lat, p.lng) for p in places)
    widest = max(per_district.values())
    thin = 0
    for district in DISTRICTS:
        count = per_district.get(district.name, 0)
        bar = BAR * max(0, round(count / widest * 24)) if widest else ""
        if count == 0:
            flag = "  ← 비었음"
        elif count < MIN_PER_DISTRICT:
            flag = f"  ← {MIN_PER_DISTRICT} 미만"
            thin += 1
        else:
            flag = ""
        print(f"  {district.name:<6} {count:>6,}  {bar}{flag}")
    if thin:
        print(f"  ※ {thin}개 상권이 {MIN_PER_DISTRICT}건 미만 — 카카오 질의 상한(45건/질의)에"
              " 걸렸을 가능성. 격자 수집이 켜진 build_places 로 다시 돌리세요.")
    outside = per_district.get("(범위 밖)", 0)
    if outside:
        print(f"  {'(범위 밖)':<6} {outside:>6,}  ← 상권 중심에서 5km 초과")

    # ② 슬롯 분류 — 플래너가 실제로 쓰는 classify 로 센다(코드 → 이름 폴백 → activity).
    #    코드만 보고 "미매핑"이라 하면 보충 키워드로 들어온 소품샵·전시가 다 미매핑으로 찍힌다.
    print("\n── 슬롯 매핑 " + "─" * 42)
    slots = Counter(classify(p) for p in places)
    by_name = sum(1 for p in places if slot_for(p.category_code, p.category) is None)
    for slot, count in sorted(slots.items()):
        print(f"  {slot:<10} {count:>6,}  {_pct(count, total)}")
    print(f"  {'이름 폴백':<10} {by_name:>6,}  {_pct(by_name, total)}"
          "  (카카오 코드 밖 → 카테고리 이름으로 분류, 정상)")

    # ③ 폐업 제거율 — 남아 있는 것 중 폐업으로 판정되는 게 있으면 필터가 샌 것이다
    print("\n── 폐업 필터 " + "─" * 42)
    from app.adapters.localdata import get_localdata_registry

    # 검증 스크립트도 별개 프로세스다 — 여기서 동기 적재하지 않으면 늘 "미적재"다
    print("  LOCALDATA 적재 중… (첫 실행은 CSV 파싱 40초 안팎, 이후는 캐시로 수 초)", flush=True)
    load_localdata_or_exit(allow_missing=True)
    registry = get_localdata_registry()
    if not registry.loaded:
        print("  LOCALDATA 미적재 — 폐업 판정이 통째로 빠져 있습니다"
              " (LOCALDATA_CSV_DIR 설정과 scripts/fetch_localdata.py 확인)")
    else:
        matched = sum(1 for p in places if registry.find(p.name, p.address))
        leaked = sum(1 for p in places if registry.is_closed(p.name, p.address))
        with_age = sum(1 for p in places if p.opened_on)
        print(f"  대장 매칭    {matched:>6,}  {_pct(matched, total)}")
        print(f"  업력 부착    {with_age:>6,}  {_pct(with_age, total)}")
        print(f"  폐업 잔존    {leaked:>6,}  {_pct(leaked, total)}"
              f"{'  ← 0 이어야 정상' if leaked else '  ✓'}")

    # ④ Google 매핑·보강 비율
    print("\n── Google 보강 " + "─" * 40)
    mapped = sum(1 for p in places if p.google_place_id)
    hours = sum(1 for p in places if p.hours_checked_at)
    rated = sum(1 for p in places if p.rating is not None)
    blog = sum(1 for p in places if p.blog_mentions is not None)
    print(f"  place_id 매핑 {mapped:>6,}  {_pct(mapped, total)}")
    print(f"  영업시간 확인 {hours:>6,}  {_pct(hours, total)}")
    print(f"  평점 확인     {rated:>6,}  {_pct(rated, total)}")
    print(f"  블로그 인지도 {blog:>6,}  {_pct(blog, total)}")
    if not mapped:
        print("  (Google 키가 없으면 0 이 정상 — 키를 넣고 배치를 다시 돌리면 이어서 채워집니다)")

    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
