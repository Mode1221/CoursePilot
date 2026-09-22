#!/usr/bin/env python
"""합의 코스 정확도 평가 — 실데이터로 시나리오를 돌려 채점한다(VM 에서 실행).

    docker compose -f docker-compose.prod.yml exec backend python scripts/eval_consensus.py
    ... --regions 성수,홍대,강남역 --out /data/localdata/eval.json

- 카카오 로컬(장소)·네이버(경로)만 호출한다. **Google 영업시간과 LLM 웹검색 폴백은 끈다**
  (유료 한도를 평가에 쓰지 않도록). 그래서 영업시간 검증은 저장된 값 기준이다.
- 결과: 화면에 요약·실패 목록, --out 에 전체 JSON.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.adapters.map_service import get_map_service  # noqa: E402
from app.batch.districts import DISTRICTS  # noqa: E402
from app.config import settings  # noqa: E402
from app.evaluation.consensus_eval import Score, default_scenarios, score, summarize  # noqa: E402
from app.pipeline.agent import generate_course  # noqa: E402

DEFAULT_REGIONS = "성수,홍대,연남,강남역,을지로,잠실,이태원,여의도"


async def run(regions: list[str], max_km: float) -> list[Score]:
    # 유료 호출 차단: Google 영업시간·평점, LLM 웹검색 폴백
    settings.google_maps_api_key = ""
    settings.hours_fallback_daily_cap = 0
    centers = {d.name: (d.lat, d.lng) for d in DISTRICTS}
    svc = get_map_service()
    scores: list[Score] = []
    scenarios = default_scenarios(regions)
    for i, scn in enumerate(scenarios, 1):
        t0 = time.monotonic()
        try:
            r = await generate_course(
                scn.request, svc, {}, None, consensus_inputs=[scn.a, scn.b], consensus_prefer=scn.b.name
            )
            summary = r.consensus.summary if r.consensus else []
            s = score(scn, r.timeline, summary, r.constraints, centers.get(scn.region),
                      yielded=r.consensus.yielded if r.consensus else None, max_km=max_km)
        except Exception as exc:  # 한 시나리오 실패가 전체를 멈추지 않는다
            s = Score(key=scn.key, region=scn.region, error=f"{type(exc).__name__}: {exc}")
        scores.append(s)
        mark = "✓" if s.passed() else "✗"
        print(f"[{i:>2}/{len(scenarios)}] {mark} {s.key:<16} {s.stops}곳 {time.monotonic() - t0:4.1f}s  "
              + " → ".join(f"{n}({c})" for n, c in zip(s.names, s.categories, strict=False)), flush=True)
    return scores


def report(scores: list[Score]) -> None:
    print("\n" + "=" * 60 + "\n요약")
    for k, v in summarize(scores).items():
        print(f"  {k:<18} {v}")
    failed = [s for s in scores if not s.passed()]
    if failed:
        print("\n실패 상세")
        for s in failed:
            why = []
            if s.error:
                why.append(s.error)
            if not s.region_ok:
                why.append(f"지역 이탈 {s.max_km}km")
            if not s.both_in_slots:
                why.append("한쪽 취향이 칸에 없음")
            if s.unfit:
                why.append(f"부적합 업태 {s.unfit}")
            if s.dislike_hits:
                why.append(f"싫은 것 포함 {s.dislike_hits}")
            if not s.travel_ok:
                why.append(f"이동 제한 초과(최대 {s.max_leg}분)")
            if s.duplicates:
                why.append("중복 장소")
            if s.stops < 2:
                why.append(f"칸 부족({s.stops})")
            if s.unmet:
                why.append(f"못 찾은 취향 {s.unmet}")
            print(f"  ✗ {s.key}: " + " / ".join(why))


def main() -> int:
    logging.basicConfig(level=logging.WARNING)
    ap = argparse.ArgumentParser(description="합의 코스 정확도 평가(실데이터)")
    ap.add_argument("--regions", default=DEFAULT_REGIONS, help="쉼표로 구분한 상권 이름(districts.py)")
    ap.add_argument("--max-km", type=float, default=2.5, help="상권 중심에서 이 거리를 넘으면 지역 이탈")
    ap.add_argument("--out", default="", help="전체 결과 JSON 경로")
    args = ap.parse_args()
    regions = [r.strip() for r in args.regions.split(",") if r.strip()]
    scores = asyncio.run(run(regions, args.max_km))
    report(scores)
    if args.out:
        Path(args.out).write_text(
            json.dumps({"summary": summarize(scores), "runs": [s.as_dict() for s in scores]}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n전체 결과: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
