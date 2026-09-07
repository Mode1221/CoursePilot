"""코스 품질 향상 플래너 (docs/AI_COURSE_QUALITY.md).

후보 스코어링(A) + 카테고리 시퀀스 템플릿(B) + 동선 최적화(C) + Best-of-N(D).
외부 키 불필요·결정론적. build_timeline 이 최종 물리 검증을 담당한다.
"""
from __future__ import annotations

from app.adapters.map_service import MapService
from app.pipeline.validation import build_timeline
from app.schemas import Place, PlanConstraints, TimelineItem

# ── 카테고리 분류 ────────────────────────────────────────────────
_SLOT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "meal": ("restaurant", "식당", "음식", "한식", "일식", "중식", "고기", "분식", "브런치"),
    "cafe": ("cafe", "카페", "디저트", "베이커리", "빵", "커피"),
    "bar": ("bar", "술", "펍", "포차", "와인", "칵테일"),
    "activity": ("전시", "갤러리", "소품", "공원", "미술", "책", "서점", "쇼핑"),
}


def classify(place: Place) -> str:
    cat = (place.category or "").lower()
    for slot, kws in _SLOT_KEYWORDS.items():
        if any(k in cat for k in kws):
            return slot
    return "activity"  # 미분류는 활동으로


# ── 후보 스코어링 (A) ────────────────────────────────────────────
def score_place(
    place: Place,
    constraints: PlanConstraints,
    prefs: dict | None,
    popularity: float = 0.0,
) -> float:
    prefs = prefs or {}
    score = 0.0

    # 평점 (0~5 → 0~1)
    if place.rating is not None:
        score += 0.4 * (place.rating / 5.0)

    # 자체 정량 신호: 인기(코스 채택·북마크). 이미 0~1 로 정규화되어 들어옴
    score += 0.25 * popularity

    # 키워드/무드 매칭 (카테고리·이름에 등장)
    haystack = f"{place.category or ''} {place.name}".lower()
    keywords = [k.lower() for k in constraints.keywords]
    if keywords:
        matched = sum(1 for k in keywords if k in haystack)
        score += 0.3 * (matched / len(keywords))

    # 예산 적합 (저렴할수록 여유 → 가점, 가격 미상은 중립)
    if constraints.budget_max and place.price is not None:
        share = place.price / max(1, constraints.budget_max)
        score += 0.2 * max(0.0, 1.0 - share)

    # 온보딩 선호 지역/무드 일치
    if prefs.get("mood") and prefs["mood"].lower() in haystack:
        score += 0.1
    return score


# ── 카테고리 시퀀스 템플릿 (B) ───────────────────────────────────
def desired_slots(constraints: PlanConstraints) -> list[str]:
    dur = constraints.duration_min or 180
    n = max(2, min(4, dur // 90))
    evening = constraints.start_time is not None and constraints.start_time.hour >= 18
    base = {
        2: ["meal", "bar" if evening else "cafe"],
        3: ["meal", "cafe", "bar" if evening else "activity"],
        4: ["meal", "activity", "cafe", "bar" if evening else "cafe"],
    }[n]
    return base


# ── 동선 최적화 (C): nearest-neighbor ────────────────────────────
def _dist(a: Place, b: Place) -> float:
    return abs(a.lat - b.lat) + abs(a.lng - b.lng)  # 맨해튼 근사(정렬용)


def route_order(places: list[Place]) -> list[Place]:
    if len(places) <= 2:
        return places
    remaining = places[1:]
    ordered = [places[0]]
    while remaining:
        last = ordered[-1]
        nxt = min(remaining, key=lambda p: _dist(last, p))
        ordered.append(nxt)
        remaining.remove(nxt)
    return ordered


# ── 후보 선택: 슬롯별 최고 점수 + 다양성 ─────────────────────────
def _pick_by_template(
    ranked: list[Place], slots: list[str]
) -> list[Place]:
    used: set[str] = set()
    picked: list[Place] = []
    for slot in slots:
        cand = next(
            (p for p in ranked if p.id not in used and classify(p) == slot), None
        )
        if cand is None:  # 해당 카테고리 없으면 미사용 최고 점수로 대체
            cand = next((p for p in ranked if p.id not in used), None)
        if cand is not None:
            picked.append(cand)
            used.add(cand.id)
    return picked


# ── 코스 목적함수 (D) ────────────────────────────────────────────
def course_score(timeline: list[TimelineItem]) -> float:
    if not timeline:
        return float("-inf")
    ratings = [it.place.rating for it in timeline if it.place.rating is not None]
    avg_rating = sum(ratings) / len(ratings) if ratings else 0.0
    total_travel = sum(
        it.travel_to_next.duration_min for it in timeline if it.travel_to_next
    )
    diversity = len({classify(it.place) for it in timeline})
    return (
        len(timeline) * 1.0          # 완성도(장소 수)
        + avg_rating * 0.5           # 평균 평점
        + diversity * 0.3            # 카테고리 다양성
        - total_travel * 0.02        # 총 이동 페널티
    )


async def plan_course(
    candidates: list[Place],
    constraints: PlanConstraints,
    map_service: MapService,
    prefs: dict | None = None,
) -> list[TimelineItem]:
    """스코어링·템플릿·동선·Best-of-N 을 적용해 최적 타임라인을 반환."""
    if not candidates:
        return []

    # 자체 인기 신호 조회 후 0~1 로 정규화(최댓값 대비 상대값)
    from app.popularity import popularity_store

    raw = popularity_store.scores([p.id for p in candidates])
    peak = max(raw.values(), default=0) or 1
    pop = {pid: v / peak for pid, v in raw.items()}

    ranked = sorted(
        candidates,
        key=lambda p: score_place(p, constraints, prefs, pop.get(p.id, 0.0)),
        reverse=True,
    )
    slots = desired_slots(constraints)

    # 후보 코스 시드 3종 → 각각 물리 검증 후 코스 점수로 최고 선택 (D)
    seeds: list[list[Place]] = []
    templated = _pick_by_template(ranked, slots)
    if templated:
        seeds.append(templated)                 # 1) 템플릿 순서
        seeds.append(route_order(templated))    # 2) 템플릿 세트의 동선 최적화
    seeds.append(ranked[: len(slots)])          # 3) 순수 점수 상위

    best: list[TimelineItem] = []
    best_score = float("-inf")
    for seed in seeds:
        timeline = await build_timeline(seed, constraints, map_service)
        s = course_score(timeline)
        if s > best_score:
            best_score, best = s, timeline
    return best
