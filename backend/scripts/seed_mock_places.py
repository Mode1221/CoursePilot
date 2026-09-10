#!/usr/bin/env python
"""시드 장소 넣기·지우기 — 키 없이 전체 흐름을 돌려 보기 위한 것.

    python scripts/seed_mock_places.py            # 상권 24곳에 시드 투입
    python scripts/seed_mock_places.py --district 성수 연남
    python scripts/seed_mock_places.py --clear    # 시드만 골라 삭제(실데이터는 건드리지 않는다)
    python scripts/seed_mock_places.py --dry-run  # 넣지 않고 분포만 본다

같은 seed 로 만들면 id 가 같아 다시 돌려도 중복이 생기지 않는다.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.adapters.kakao import slot_for  # noqa: E402
from app.batch.db_setup import connect_db  # noqa: E402
from app.batch.districts import DISTRICTS  # noqa: E402
from app.batch.seed import seed_places  # noqa: E402


def _summary(places) -> None:
    slots = Counter(slot_for(p.category_code, p.category) or "미매핑" for p in places)
    prices = [p.price for p in places if p.price]
    print(f"장소 {len(places):,}건")
    print("  슬롯: " + ", ".join(f"{k} {v:,}" for k, v in sorted(slots.items())))
    if prices:
        prices.sort()
        mid = prices[len(prices) // 2]
        print(f"  1인 비용: {min(prices):,}~{max(prices):,}원 (중앙값 {mid:,}원)")
    rated = [p for p in places if p.rating]
    print(f"  평점 있는 곳: {len(rated):,}건 ({len(rated) / len(places) * 100:.0f}%)")


def main() -> int:
    ap = argparse.ArgumentParser(description="시드 장소 투입/삭제")
    ap.add_argument("--district", nargs="*", help="상권 이름(기본: 전체)")
    ap.add_argument("--clear", action="store_true", help="시드 장소만 삭제")
    ap.add_argument("--dry-run", action="store_true", help="저장하지 않고 분포만 출력")
    ap.add_argument("--seed", type=int, default=20260910, help="난수 시드(같으면 같은 결과)")
    args = ap.parse_args()

    targets = DISTRICTS
    if args.district:
        names = set(args.district)
        targets = tuple(d for d in DISTRICTS if d.name in names)
        if not targets:
            print(f"알 수 없는 상권: {', '.join(sorted(names))}", file=sys.stderr)
            return 1

    if not args.dry_run and not connect_db():
        print("DB 에 연결하지 못했습니다 — 시드를 넣어도 남지 않습니다.", file=sys.stderr)
        return 1

    from app.places import place_repo

    if args.clear:
        stored = place_repo.all(limit=200_000)
        mock_ids = [p.id for p in stored if p.is_mock]
        removed = place_repo.delete_many(mock_ids) if mock_ids else 0
        print(f"시드 장소 {removed:,}건 삭제 (실데이터 {len(stored) - len(mock_ids):,}건은 유지)")
        return 0

    places = seed_places(targets, seed=args.seed)
    _summary(places)
    if args.dry_run:
        print("(--dry-run: 저장하지 않았습니다)")
        return 0

    place_repo.upsert_many(places)
    print(f"저장 완료 — 상권 {len(targets)}곳")
    print("※ 가짜 데이터입니다. 실데이터가 들어오면 --clear 로 한 번에 지우세요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
