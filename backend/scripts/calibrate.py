#!/usr/bin/env python
"""라벨 JSONL 로 장소 스코어 계수를 오프라인 캘리브레이션한다.

    python scripts/calibrate.py labels.jsonl

현재 계수의 랭킹 품질과 탐색 결과를 출력할 뿐, 코드를 바꾸지는 않는다.
납득이 되면 app/pipeline/weights.py 의 기본값을 손으로 갱신한다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.pipeline.calibration import (  # noqa: E402
    calibrate,
    diff_weights,
    evaluate,
    load_samples,
)
from app.pipeline.weights import PLACE_WEIGHTS  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="장소 스코어 계수 캘리브레이션")
    ap.add_argument("labels", help="라벨 JSONL 경로")
    ap.add_argument("--rounds", type=int, default=2, help="좌표 상승 반복 횟수")
    ap.add_argument("--json", action="store_true", help="JSON 으로 출력")
    args = ap.parse_args()

    samples = load_samples(args.labels)
    before = evaluate(samples, PLACE_WEIGHTS)
    tuned, after = calibrate(samples, PLACE_WEIGHTS, rounds=args.rounds)
    changed = diff_weights(PLACE_WEIGHTS, tuned)

    if args.json:
        print(json.dumps(
            {"before": before.as_dict(), "after": after.as_dict(), "changed": changed},
            ensure_ascii=False,
            indent=2,
        ))
        return 0

    print(f"샘플 {before.samples}건")
    print(f"현재  top1={before.top1} top3={before.top3} mrr={before.mrr}")
    print(f"탐색  top1={after.top1} top3={after.top3} mrr={after.mrr}")
    if not changed:
        print("개선 없음 — 현재 계수 유지")
        return 0
    print("바뀐 계수:")
    for name, (old, new) in changed.items():
        print(f"  {name}: {old} → {new}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
