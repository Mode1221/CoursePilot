#!/usr/bin/env python
"""핫플 신호 + 진행 중인 팝업·행사 갱신(매일 새벽 크론).

    docker compose -f docker-compose.prod.yml exec backend python scripts/refresh_hot.py
    ... --only popups   (팝업·행사만)   --only hot   (핫플 점수만)
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.adapters.map_service import get_map_service  # noqa: E402
from app.batch.hot_refresh import refresh_hotness, refresh_popups  # noqa: E402
from app.places import place_repo  # noqa: E402


async def main(only: str) -> None:
    if only in ("all", "hot"):
        places = place_repo.all(limit=100_000)
        updated = await refresh_hotness(places)
        place_repo.upsert_many(updated)
        hot = [p for p in updated if p.hot_score]
        print(f"핫플 신호: {len(updated)}곳 확인, 요즘 뜨는 곳 {len(hot)}곳")
        for p in sorted(hot, key=lambda x: -(x.hot_score or 0))[:15]:
            print(f"  {p.hot_score:.2f} {p.name}  {', '.join(p.hot_reasons)}  (협찬 {p.sponsored_ratio})")
    if only in ("all", "popups"):
        pops = await refresh_popups(get_map_service())
        print(f"진행 중인 팝업·행사: {len(pops)}곳")
        for p in pops[:20]:
            print(f"  ~{p.active_until}  {p.name}  ({p.address or ''})")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["all", "hot", "popups"], default="all")
    asyncio.run(main(ap.parse_args().only))
