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
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.adapters.map_service import get_map_service  # noqa: E402
from app.batch.db_setup import connect_db  # noqa: E402
from app.batch.hot_refresh import refresh_hotness, refresh_popups  # noqa: E402
from app.places import place_repo  # noqa: E402


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


async def main(only: str, force: bool = False) -> None:
    # 다른 배치와 같이 DB 부터 연결한다 — 안 하면 인메모리(빈) 저장소를 읽어 "0곳 확인"이 된다(실측)
    if not connect_db():
        print("✗ DB 에 연결하지 못했어요 — 핫플 신호를 저장할 수 없어 중단합니다")
        raise SystemExit(1)
    t0 = time.monotonic()
    if only in ("all", "hot"):
        places = place_repo.all(limit=100_000)
        _log(f"핫플 신호 시작 — 저장된 장소 {len(places)}곳")

        def progress(name: str, n: int, total: int, batch: list) -> None:
            # 상권마다 바로 저장한다 — 중간에 꺼도 여기까지 한 건 남는다
            if batch:
                place_repo.upsert_many(batch)
            hot = sum(1 for p in batch if p.hot_score)
            _log(f"  ({n}/{total}) {name}: {len(batch)}곳 확인, 뜨는 곳 {hot}  · {time.monotonic() - t0:.0f}s")

        updated = await refresh_hotness(places, on_district=progress, force=force)
        hot = [p for p in updated if p.hot_score]
        _log(f"핫플 신호: {len(updated)}곳 확인, 요즘 뜨는 곳 {len(hot)}곳")
        shown: set[str] = set()
        top = []
        for p in sorted(hot, key=lambda x: -(x.hot_score or 0)):
            if p.name not in shown:
                shown.add(p.name)
                top.append(p)
        for p in top[:15]:
            print(f"  {p.hot_score:.2f} {p.name}  {', '.join(p.hot_reasons)}  (협찬 {p.sponsored_ratio})")
    if only in ("all", "popups"):
        _log("팝업·행사 시작")
        pops = await refresh_popups(
            get_map_service(),
            on_district=lambda name, n, total, found: _log(f"  ({n}/{total}) {name} · 지금까지 {found}곳"),
        )
        _log(f"진행 중인 팝업·행사: {len(pops)}곳")
        for p in pops[:20]:
            print(f"  ~{p.active_until}  {p.name}  ({p.address or ''})")
    _log(f"끝 — {time.monotonic() - t0:.0f}초")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["all", "hot", "popups"], default="all")
    ap.add_argument("--force", action="store_true", help="7일 재확인 주기를 무시하고 다시 본다(기준을 바꾼 뒤)")
    args = ap.parse_args()
    asyncio.run(main(args.only, args.force))
