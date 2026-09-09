"""계수 캘리브레이션 하네스."""
from __future__ import annotations

import json

from app.pipeline.calibration import (
    Sample,
    calibrate,
    diff_weights,
    evaluate,
    load_samples,
)
from app.pipeline.planner import score_place
from app.pipeline.weights import PLACE_WEIGHTS, ScoreWeights
from app.schemas import Place, PlanConstraints


def _place(pid: str, *, name="가게", category="음식점>한식", rating=None, price=None) -> Place:
    return Place(
        id=pid, name=name, category=category, lat=37.5, lng=127.0,
        rating=rating, price=price,
    )


def _sample(chosen: str, candidates: list[Place], **kw) -> Sample:
    return Sample(
        constraints=PlanConstraints(region="성수동", **kw),
        candidates=candidates,
        chosen_id=chosen,
    )


def test_평가지표는_순위를_반영한다():
    cands = [_place("a", rating=5.0), _place("b", rating=1.0)]
    top = evaluate([_sample("a", cands)])
    bottom = evaluate([_sample("b", cands)])
    assert top.top1 == 1.0 and top.mrr == 1.0
    assert bottom.top1 == 0.0 and bottom.mrr == 0.5
    assert bottom.top3 == 1.0


def test_샘플이_없으면_0():
    r = evaluate([])
    assert r.samples == 0 and r.mrr == 0.0


def test_캘리브레이션이_예산_계수를_찾아낸다():
    # 라벨은 항상 "싼 쪽" — 평점은 비싼 쪽이 높게 깔아 예산 신호를 눌러둔다
    samples = []
    for i in range(6):
        cheap = _place(f"c{i}", rating=3.0, price=10000)
        pricey = _place(f"p{i}", rating=5.0, price=60000)
        samples.append(_sample(cheap.id, [cheap, pricey], budget_max=60000))
    base = PLACE_WEIGHTS.replace(budget=0.05)
    before = evaluate(samples, base)
    tuned, after = calibrate(samples, base)
    assert before.top1 == 0.0
    assert after.top1 == 1.0
    assert diff_weights(base, tuned)  # 계수가 실제로 움직였다


def test_개선이_없으면_계수를_그대로_둔다():
    samples = [_sample("a", [_place("a", rating=5.0), _place("b", rating=1.0)])]
    tuned, _ = calibrate(samples)
    assert tuned == PLACE_WEIGHTS
    assert diff_weights(PLACE_WEIGHTS, tuned) == {}


def test_가중치_주입이_점수를_바꾼다():
    p = _place("a", rating=5.0)
    c = PlanConstraints(region="성수동")
    high = score_place(p, c, None, weights=ScoreWeights(rating=1.0))
    low = score_place(p, c, None, weights=ScoreWeights(rating=0.0))
    assert high > low
    assert score_place(p, c, None) == score_place(p, c, None, weights=PLACE_WEIGHTS)


def test_라벨_파일을_읽는다(tmp_path):
    row = {
        "constraints": {"region": "성수동"},
        "candidates": [
            {"id": "a", "name": "가", "lat": 37.5, "lng": 127.0, "rating": 4.5},
            {"id": "b", "name": "나", "lat": 37.5, "lng": 127.0},
        ],
        "chosen_id": "a",
    }
    path = tmp_path / "labels.jsonl"
    path.write_text(json.dumps(row, ensure_ascii=False) + "\n\n", encoding="utf-8")
    samples = load_samples(path)
    assert len(samples) == 1
    assert samples[0].chosen_id == "a"
    assert evaluate(samples).top1 == 1.0
