"""합성 사용 신호 리플레이 (학습 루프 검증용).

실사용 데이터가 0인 단계에서도 "신호가 쌓이면 추천이 실제로 나아지는가"를
확인할 수 있어야 한다. 숨은 선호(hidden utility)를 가진 가상 사용자가 코스를
고르게 하고, 그 채택을 popularity/timecontext/cooccurrence/sequence 스토어에
그대로 흘려보낸 뒤 랭킹 품질 변화를 잰다. 결정론적(시드 고정)이라 CI 에서도 돈다.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import time

from app.pipeline.calibration import Report, Sample
from app.pipeline.planner import classify, score_place
from app.schemas import Place, PlanConstraints

# 합성 카탈로그: 카테고리 × 품질 등급. 숨은 선호는 "이름에 든 등급"이다.
_CATEGORIES = {
    "meal": "음식점>한식",
    "cafe": "카페>디저트",
    "bar": "술집>포차",
    "activity": "문화,예술>전시",
}
# 숨은 선호: 시간대별로 잘 채택되는 슬롯(현실의 브런치/야간 술자리 패턴)
_DAYPART_SLOTS = {
    "morning": ("cafe", "meal"),
    "afternoon": ("meal", "activity"),
    "evening": ("meal", "bar"),
}
CATALOG_PER_SLOT = 5  # 슬롯당 후보 수


@dataclass(frozen=True)
class Session:
    """가상 사용자가 한 번 코스를 만든 기록."""

    hour: int
    slots: tuple[str, ...]
    place_ids: tuple[str, ...]


def build_catalog() -> list[Place]:
    """슬롯별 후보 장소. 외부 평점은 숨은 선호와 일부러 어긋나게 둔다."""
    places: list[Place] = []
    for slot, category in _CATEGORIES.items():
        for i in range(CATALOG_PER_SLOT):
            places.append(
                Place(
                    id=f"{slot}-{i}",
                    name=f"{slot}{i}",
                    category=category,
                    lat=37.54 + i * 0.001,
                    lng=127.05 + i * 0.001,
                    # 평점은 숨은 선호와 반대로 — 평점만 보면 못 맞힌다
                    rating=round(3.0 + i * 0.4, 1),
                    price=15000,
                )
            )
    return places


def _hidden_pick(rng: random.Random, slot: str, hour: int) -> str:
    """숨은 선호: 슬롯마다 0번 후보가 가장 자주 채택된다(약간의 잡음 포함)."""
    weights = [0.5, 0.22, 0.13, 0.09, 0.06][:CATALOG_PER_SLOT]
    idx = rng.choices(range(CATALOG_PER_SLOT), weights=weights)[0]
    return f"{slot}-{idx}"


def simulate_sessions(count: int, *, seed: int = 7) -> list[Session]:
    """가상 세션 생성(결정론적)."""
    from app.timecontext import daypart_of

    rng = random.Random(seed)
    sessions: list[Session] = []
    for _ in range(count):
        hour = rng.choice([10, 13, 15, 19, 20])
        slots = _DAYPART_SLOTS[daypart_of(hour)]
        ids = tuple(_hidden_pick(rng, slot, hour) for slot in slots)
        sessions.append(Session(hour=hour, slots=tuple(slots), place_ids=ids))
    return sessions


def replay(sessions: list[Session]) -> None:
    """세션을 실제 신호 스토어에 흘려보낸다(운영과 동일한 경로)."""
    from app.cooccurrence import cooccurrence_store
    from app.popularity import popularity_store
    from app.sequence import sequence_store
    from app.timecontext import daypart_of, time_context_store

    catalog = {p.id: p for p in build_catalog()}
    for s in sessions:
        ids = list(s.place_ids)
        popularity_store.bump_many(ids)
        time_context_store.bump_many(ids, daypart_of(s.hour))
        cooccurrence_store.bump_course(ids)
        sequence_store.bump_sequence([classify(catalog[i]) for i in ids])


def to_samples(sessions: list[Session]) -> list[Sample]:
    """세션 → 캘리브레이션/평가용 라벨 샘플(슬롯별 후보 vs 채택 1건)."""
    catalog = build_catalog()
    by_slot: dict[str, list[Place]] = {}
    for p in catalog:
        by_slot.setdefault(p.id.split("-")[0], []).append(p)
    samples: list[Sample] = []
    for s in sessions:
        for slot, chosen in zip(s.slots, s.place_ids, strict=True):
            samples.append(
                Sample(
                    constraints=PlanConstraints(
                        region="성수동", start_time=time(s.hour, 0)
                    ),
                    candidates=list(by_slot[slot]),
                    chosen_id=chosen,
                )
            )
    return samples


def rank_quality(samples: list[Sample]) -> Report:
    """현재 신호 스토어를 반영한 랭킹 품질(top1/top3/MRR).

    `calibration.evaluate` 와 달리 인기·시간대 신호를 실제로 조회한다 —
    학습 루프가 도는지 보려면 그 신호가 점수에 들어가야 하기 때문.
    """
    from app.popularity import popularity_store
    from app.timecontext import daypart_of, time_context_store

    if not samples:
        return Report(0, 0.0, 0.0, 0.0)
    hits1 = hits3 = 0
    rr = 0.0
    for s in samples:
        ids = [p.id for p in s.candidates]
        raw_pop = popularity_store.scores(ids)
        peak = max(raw_pop.values(), default=0.0)
        hour = s.constraints.start_time.hour if s.constraints.start_time else 12
        raw_ctx = time_context_store.scores(ids, daypart_of(hour))
        ctx_peak = max(raw_ctx.values(), default=0.0)
        scored = [
            (
                score_place(
                    p,
                    s.constraints,
                    s.prefs,
                    popularity=(raw_pop.get(p.id, 0.0) / peak) if peak else 0.0,
                    context_pop=(raw_ctx.get(p.id, 0.0) / ctx_peak) if ctx_peak else 0.0,
                ),
                p.id,
            )
            for p in s.candidates
        ]
        scored.sort(key=lambda t: (-t[0], t[1]))
        ranked = [pid for _, pid in scored]
        rank = ranked.index(s.chosen_id) + 1
        hits1 += rank == 1
        hits3 += rank <= 3
        rr += 1 / rank
    n = len(samples)
    return Report(n, round(hits1 / n, 4), round(hits3 / n, 4), round(rr / n, 4))
