"""목적함수 계수 오프라인 캘리브레이션.

라벨(사용자가 실제 고른 장소)을 담은 샘플로 현재 계수의 top-1 정확도·MRR 를
재고, 좌표 상승(coordinate ascent)으로 더 나은 계수를 탐색한다.
외부 키·네트워크 불필요하고 결정론적이라 CI 에서도 돌릴 수 있다.

라벨 소스: `app.outcome` 의 채택 로그를 JSONL 로 내보낸 것(운영), 또는
시뮬레이션 신호(개발). `load_samples` 가 두 경우 모두 같은 형태로 읽는다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.pipeline.planner import score_place
from app.pipeline.weights import PLACE_WEIGHTS, ScoreWeights
from app.schemas import Place, PlanConstraints

# 계수 하나를 훑을 때 쓰는 배율. 1.0 을 포함해 현재 값이 항상 후보에 남는다.
DEFAULT_MULTIPLIERS = (0.0, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0)


@dataclass(frozen=True)
class Sample:
    """후보 목록과 그중 실제로 채택된 장소 하나."""

    constraints: PlanConstraints
    candidates: list[Place]
    chosen_id: str
    prefs: dict | None = None

    def ranked_ids(self, weights: ScoreWeights) -> list[str]:
        scored = [
            (score_place(p, self.constraints, self.prefs, weights=weights), p.id)
            for p in self.candidates
        ]
        # 점수 내림차순, 동점은 id 오름차순 → 결정론적
        scored.sort(key=lambda t: (-t[0], t[1]))
        return [pid for _, pid in scored]


@dataclass(frozen=True)
class Report:
    samples: int
    top1: float  # 1순위 적중률
    top3: float
    mrr: float  # 평균 역순위

    def as_dict(self) -> dict:
        return {"samples": self.samples, "top1": self.top1, "top3": self.top3, "mrr": self.mrr}


def evaluate(samples: list[Sample], weights: ScoreWeights | None = None) -> Report:
    """샘플 집합에 대한 랭킹 품질."""
    w = weights or PLACE_WEIGHTS
    if not samples:
        return Report(0, 0.0, 0.0, 0.0)
    hits1 = hits3 = 0
    rr = 0.0
    for s in samples:
        ranked = s.ranked_ids(w)
        if s.chosen_id not in ranked:
            continue
        rank = ranked.index(s.chosen_id) + 1
        hits1 += rank == 1
        hits3 += rank <= 3
        rr += 1 / rank
    n = len(samples)
    return Report(n, round(hits1 / n, 4), round(hits3 / n, 4), round(rr / n, 4))


def calibrate(
    samples: list[Sample],
    base: ScoreWeights | None = None,
    *,
    multipliers: tuple[float, ...] = DEFAULT_MULTIPLIERS,
    rounds: int = 2,
) -> tuple[ScoreWeights, Report]:
    """좌표 상승으로 MRR 을 높이는 계수를 찾는다(결정론적).

    개선이 없으면 기존 계수를 그대로 돌려주므로, 데이터가 부족할 때
    엉뚱한 값으로 튀지 않는다.
    """
    best = base or PLACE_WEIGHTS
    best_report = evaluate(samples, best)
    if not samples:
        return best, best_report
    for _ in range(rounds):
        improved = False
        for name in ScoreWeights.field_names():
            if name == "self_rating_share":
                continue  # 0~1 비중이라 배율 탐색 대상이 아니다
            current = getattr(best, name)
            for m in multipliers:
                cand = best.replace(**{name: round(current * m, 4)})
                if cand == best:
                    continue
                report = evaluate(samples, cand)
                if _better(report, best_report):
                    best, best_report, improved = cand, report, True
        if not improved:
            break
    return best, best_report


def _better(a: Report, b: Report) -> bool:
    return (a.mrr, a.top1) > (b.mrr, b.top1)


def load_samples(path: str | Path) -> list[Sample]:
    """JSONL 라벨 파일 → 샘플. 한 줄이 한 요청이다.

    형식: {"constraints": {...}, "candidates": [Place...], "chosen_id": "...",
           "prefs": {...}}
    """
    samples: list[Sample] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        raw = json.loads(line)
        samples.append(
            Sample(
                constraints=PlanConstraints.model_validate(raw["constraints"]),
                candidates=[Place.model_validate(p) for p in raw["candidates"]],
                chosen_id=raw["chosen_id"],
                prefs=raw.get("prefs"),
            )
        )
    return samples


def diff_weights(before: ScoreWeights, after: ScoreWeights) -> dict[str, tuple[float, float]]:
    """바뀐 계수만 (이전, 이후) 로."""
    return {
        name: (getattr(before, name), getattr(after, name))
        for name in ScoreWeights.field_names()
        if getattr(before, name) != getattr(after, name)
    }
