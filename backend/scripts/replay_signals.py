#!/usr/bin/env python
"""합성 사용 신호를 리플레이해 학습 루프 효과를 측정한다.

    python scripts/replay_signals.py --sessions 300

실사용 데이터가 없을 때 "신호가 쌓이면 랭킹이 좋아지는가"를 눈으로 확인하는 용도.
캘리브레이션 라벨(JSONL)도 함께 뽑을 수 있다: --dump labels.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.pipeline.simulation import (  # noqa: E402
    rank_quality,
    replay,
    simulate_sessions,
    to_samples,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="합성 신호 리플레이")
    ap.add_argument("--sessions", type=int, default=300, help="학습용 세션 수")
    ap.add_argument("--eval-sessions", type=int, default=80, help="평가용 세션 수")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--dump", help="평가 샘플을 라벨 JSONL 로 저장할 경로")
    args = ap.parse_args()

    train = simulate_sessions(args.sessions, seed=args.seed)
    test = to_samples(simulate_sessions(args.eval_sessions, seed=args.seed + 1000))

    before = rank_quality(test)
    replay(train)
    after = rank_quality(test)

    print(f"학습 세션 {len(train)} / 평가 샘플 {before.samples}")
    print(f"리플레이 전  top1={before.top1} top3={before.top3} mrr={before.mrr}")
    print(f"리플레이 후  top1={after.top1} top3={after.top3} mrr={after.mrr}")

    if args.dump:
        with Path(args.dump).open("w", encoding="utf-8") as f:
            for s in test:
                f.write(json.dumps(
                    {
                        "constraints": json.loads(s.constraints.model_dump_json()),
                        "candidates": [
                            json.loads(p.model_dump_json()) for p in s.candidates
                        ],
                        "chosen_id": s.chosen_id,
                    },
                    ensure_ascii=False,
                ) + "\n")
        print(f"라벨 저장: {args.dump}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
