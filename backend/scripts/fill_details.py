#!/usr/bin/env python
"""영업시간·평점을 지금 바로 채운다 — 핵심 후보(상권 × 칸별 상위)부터, 기본은 이번 달 **무료 한도 안에서만**.

    python scripts/fill_details.py              # 이번 달 남은 무료(1,000건 중 남은 만큼)까지
    python scripts/fill_details.py --limit 100  # 최대 100곳
    python scripts/fill_details.py --paid       # 무료 한도를 넘어도(GOOGLE_DETAILS_MONTHLY 까지) 채운다

하루 상한(GOOGLE_DETAILS_PER_DAY + 20)과 Google 콘솔 일일 할당량에도 걸린다. 처음 채우는 곳은 place id 를
Text Search(무료)로 먼저 찾으므로 콘솔 SearchTextRequest 일일 할당량도 여유가 있어야 한다.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.batch.db_setup import connect_db  # noqa: E402
from app.batch.lock import LockBusy, batch_lock  # noqa: E402

FREE_MONTHLY = 1_000  # Place Details Enterprise 월 무료


async def fill(limit: int | None, paid: bool) -> None:
    from app.adapters.google import get_places_client, hours_stale, rating_stale
    from app.batch.places_build import core_targets
    from app.places import place_repo
    from app.quota import quota_store

    client = get_places_client()
    if not client.enabled:
        print("Google 키가 없어 채울 수 없습니다(GOOGLE_MAPS_API_KEY).")
        return
    used = quota_store.used("google.details")
    cap = quota_store.limit("google.details") or FREE_MONTHLY
    if not paid:
        cap = min(cap, FREE_MONTHLY)
    room = max(0, cap - used)
    budget = room if limit is None else min(limit, room)
    places = place_repo.all(limit=200_000)
    core = core_targets(places)
    todo = [p for p in core if hours_stale(p) or rating_stale(p)]
    print(f"이번 달 사용 {used}건 / 상한 {cap}건({'유료 포함' if paid else '무료만'}) → 이번에 최대 {budget}곳")
    print(f"저장 장소 {len(places)}곳 · 핵심 후보 {len(core)}곳 · 채울 곳 {len(todo)}곳")
    targets = todo[:budget]
    if not targets:
        print("채울 곳이 없거나 남은 한도가 없습니다.")
        return
    filled = 0
    for i in range(0, len(targets), 10):  # 10곳씩 — 분당 할당량(600)에 여유
        chunk = targets[i : i + 10]
        await asyncio.gather(*(client.refresh_details(p) for p in chunk), return_exceptions=True)
        place_repo.upsert_many(chunk)
        filled += sum(1 for p in chunk if p.hours_checked_at is not None)
        if quota_store.used("google.details") >= cap:
            break
    done = sum(1 for p in core if not hours_stale(p))
    print(f"채움 {filled}곳 · 핵심 후보 중 영업시간 확인 {done}/{len(core)}곳 ({done * 100 // max(1, len(core))}%)")
    print(f"이번 달 사용 {quota_store.used('google.details')}건 (무료 {FREE_MONTHLY}건)")


def main() -> int:
    ap = argparse.ArgumentParser(description="영업시간·평점 지금 채우기")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--paid", action="store_true", help="무료 한도를 넘어 GOOGLE_DETAILS_MONTHLY 까지")
    args = ap.parse_args()
    connect_db()
    try:
        with batch_lock("places_refresh"):
            asyncio.run(fill(args.limit, args.paid))
    except LockBusy as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
