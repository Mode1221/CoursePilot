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
    self_rating: float | None = None,
    context_pop: float = 0.0,
) -> float:
    prefs = prefs or {}
    score = 0.0

    # 평점: 자체 원탭 별점이 있으면 외부 별점과 블렌드(자체 우선), 없으면 외부만
    ext = (place.rating / 5.0) if place.rating is not None else None
    own = (self_rating / 5.0) if self_rating is not None else None
    if own is not None and ext is not None:
        score += 0.4 * (0.6 * own + 0.4 * ext)
    elif own is not None:
        score += 0.4 * own
    elif ext is not None:
        score += 0.4 * ext

    # 자체 정량 신호: 인기(코스 채택·북마크). 이미 0~1 로 정규화되어 들어옴
    score += 0.25 * popularity

    # 시간대 컨텍스트(#12): 요청 시간대에 자주 채택된 장소 가점(0~1 정규화)
    score += 0.15 * context_pop

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

    # 동행유형 컨텍스트: 상황에 맞는 장소 특성 가점
    comp_kw = _COMPANION_KEYWORDS.get(constraints.companion or "", ())
    if comp_kw and any(k in haystack for k in comp_kw):
        score += 0.15
    return score


# 동행유형별 선호 특성(이름/카테고리에 등장 시 가점)
_COMPANION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "데이트": ("분위기", "뷰", "루프탑", "야경", "감성"),
    "회식": ("룸", "단체", "고기", "포차", "호프"),
    "가족": ("한정식", "좌식", "룸", "브런치", "공원"),
    "친구": ("가성비", "핫플", "브런치"),
    "혼자": ("바", "카운터", "조용"),
}


# ── 카테고리 시퀀스 템플릿 (B) ───────────────────────────────────
def desired_slots(constraints: PlanConstraints) -> list[str]:
    dur = constraints.duration_min or 180
    n = max(2, min(4, dur // 90))
    evening = constraints.start_time is not None and constraints.start_time.hour >= 18
    comp = constraints.companion

    # 회식: 식사+술 중심 / 데이트: 활동·분위기 포함 / 가족: 술 배제·활동 위주
    if comp == "회식":
        return {2: ["meal", "bar"], 3: ["meal", "cafe", "bar"], 4: ["meal", "cafe", "bar", "bar"]}[n]
    if comp == "가족":
        return {2: ["meal", "cafe"], 3: ["meal", "activity", "cafe"], 4: ["meal", "activity", "cafe", "activity"]}[n]

    last = "bar" if (evening and comp != "가족") else ("activity" if comp == "데이트" else "cafe")
    base = {
        2: ["meal", "cafe" if comp == "데이트" else ("bar" if evening else "cafe")],
        3: ["meal", "cafe", last],
        4: ["meal", "activity", "cafe", last],
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


# ── 선호 순서 정렬 (C'): 학습된 카테고리 전이 최대화 (data #7) ──
def seq_order(places: list[Place]) -> list[Place]:
    if len(places) <= 2:
        return places
    from app.sequence import sequence_store

    # 첫 장소는 유지(식사 시작 관성), 이후 학습 전이가 가장 높은 순으로 그리디 연결
    ordered = [places[0]]
    remaining = places[1:]
    while remaining:
        last = classify(ordered[-1])
        nxt = max(remaining, key=lambda p: sequence_store.transition(last, classify(p)))
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
    # 재정렬 패턴(#7): 학습된 선호 순서(카테고리 전이)에 가점
    from app.sequence import sequence_store

    seq_pref = sequence_store.sequence_score([classify(it.place) for it in timeline])
    return (
        len(timeline) * 1.0          # 완성도(장소 수)
        + avg_rating * 0.5           # 평균 평점
        + diversity * 0.3            # 카테고리 다양성
        + _seq_norm(seq_pref)        # 선호 순서 적합
        - total_travel * 0.02        # 총 이동 페널티
    )


def _seq_norm(raw: float) -> float:
    """전이 누적값을 포화(0~0.5)로 눌러 과적합 방지."""
    if raw <= 0:
        return 0.0
    return 0.5 * (raw / (raw + 3.0))


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
    from app.ratings import rating_store

    ids = [p.id for p in candidates]
    raw = popularity_store.scores(ids)
    # 카테고리(식당/카페/…)별 최댓값으로 정규화 → 절대 인기 편향 제거(상대 인기)
    cat_peak: dict[str, float] = {}
    for p in candidates:
        c = classify(p)
        cat_peak[c] = max(cat_peak.get(c, 0.0), raw.get(p.id, 0.0))
    pop = {
        p.id: (raw.get(p.id, 0.0) / cat_peak[classify(p)])
        if cat_peak.get(classify(p))
        else 0.0
        for p in candidates
    }
    self_ratings = rating_store.averages(ids)  # 자체 원탭 별점

    # 시간대 컨텍스트(#12): 요청 시작 시간대의 채택 신호를 카테고리별 상대 정규화
    ctx_pop: dict[str, float] = {}
    if constraints.start_time is not None:
        from app.timecontext import daypart_of, time_context_store

        dp = daypart_of(constraints.start_time.hour)
        ctx_raw = time_context_store.scores(ids, dp)
        ctx_peak: dict[str, float] = {}
        for p in candidates:
            c = classify(p)
            ctx_peak[c] = max(ctx_peak.get(c, 0.0), ctx_raw.get(p.id, 0.0))
        ctx_pop = {
            p.id: (ctx_raw.get(p.id, 0.0) / ctx_peak[classify(p)])
            if ctx_peak.get(classify(p))
            else 0.0
            for p in candidates
        }

    ranked = sorted(
        candidates,
        key=lambda p: score_place(
            p, constraints, prefs, pop.get(p.id, 0.0), self_ratings.get(p.id),
            ctx_pop.get(p.id, 0.0),
        ),
        reverse=True,
    )
    slots = desired_slots(constraints)

    # 후보 코스 시드 3종 → 각각 물리 검증 후 코스 점수로 최고 선택 (D)
    seeds: list[list[Place]] = []
    templated = _pick_by_template(ranked, slots)
    if templated:
        seeds.append(templated)                 # 1) 템플릿 순서
        seeds.append(route_order(templated))    # 2) 템플릿 세트의 동선 최적화
        seeds.append(seq_order(templated))      # 3) 학습된 선호 순서(#7)
    seeds.append(ranked[: len(slots)])          # 4) 순수 점수 상위

    best: list[TimelineItem] = []
    best_score = float("-inf")
    for seed in seeds:
        timeline = await build_timeline(seed, constraints, map_service)
        s = course_score(timeline)
        if s > best_score:
            best_score, best = s, timeline
    return best
