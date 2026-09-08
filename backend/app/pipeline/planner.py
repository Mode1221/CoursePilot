"""코스 품질 향상 플래너 (docs/AI_COURSE_QUALITY.md).

후보 스코어링(A) + 카테고리 시퀀스 템플릿(B) + 동선 최적화(C) + Best-of-N(D).
외부 키 불필요·결정론적. build_timeline 이 최종 물리 검증을 담당한다.
"""
from __future__ import annotations

from datetime import time

from app.adapters.map_service import MapService
from app.pipeline.validation import build_timeline
from app.schemas import Place, PlanConstraints, TimelineItem

# ── 카테고리 분류 ────────────────────────────────────────────────
_SLOT_KEYWORDS: dict[str, tuple[str, ...]] = {
    # 네이버 지역검색 category 는 "음식점>양식" 처럼 오므로 실제 표기를 폭넓게 담는다
    "meal": (
        "restaurant", "식당", "음식", "한식", "일식", "중식", "양식", "고기", "분식", "브런치",
        "이탈리", "국수", "치킨", "피자", "돈까스", "횟집", "해물", "뷔페", "구이", "찌개",
    ),
    "cafe": ("cafe", "카페", "디저트", "베이커리", "빵", "커피", "티하우스", "찻집"),
    # "예술"이 "술"에 걸려 술집으로 오분류되던 문제 → 구체 표기만 본다
    "bar": ("bar", "술집", "포장마차", "펍", "포차", "와인", "칵테일", "주점", "호프", "이자카야", "위스키"),
    "activity": (
        "전시", "갤러리", "소품", "공원", "미술", "책", "서점", "쇼핑",
        "영화", "볼링", "방탈출", "노래", "박물관", "체험", "공연", "보드게임",
    ),
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
    cold_start: bool = False,
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

    # 콜드스타트 폴백(활용): 행동 신호가 전무하면 외부 평점에 더 의존(폴백 체인).
    # 신호가 쌓이면 자동으로 가중이 사라져 행동 기반으로 이행.
    if cold_start and ext is not None:
        score += 0.2 * ext

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

    # 행동 선호(#13): 사용자가 실제 자주 채택한 카테고리면 가점(선언보다 행동 신뢰)
    behavior_cats = prefs.get("behavior_cats") or []
    if behavior_cats and classify(place) in behavior_cats:
        score += 0.15

    # 동행유형 컨텍스트: 상황에 맞는 장소 특성 가점
    comp_kw = _COMPANION_KEYWORDS.get(constraints.companion or "", ())
    if comp_kw and any(k in haystack for k in comp_kw):
        score += 0.15

    # 제외 조건: 사용자가 빼달라고 한 성격이면 크게 감점(하드에 가까운 소프트 제약)
    if any(k.lower() in haystack for k in constraints.exclude_keywords):
        score -= 0.5

    # 우천 대체: 야외 성격은 감점, 실내 성격은 가점
    if constraints.prefer_indoor:
        if any(k in haystack for k in _OUTDOOR_KEYWORDS):
            score -= 0.4
        if any(k in haystack for k in _INDOOR_KEYWORDS):
            score += 0.15

    # 인원수 컨텍스트: 대인원은 단체석, 소수는 조용한 자리 쪽이 실패가 적다
    party_kw = _party_keywords(constraints.party_size)
    if party_kw and any(k in haystack for k in party_kw):
        score += 0.1
    return score


# 우천 시 피해야 할/선호할 장소 성격
_OUTDOOR_KEYWORDS = ("공원", "산책", "야외", "루프탑", "테라스", "시장", "한강", "캠핑", "피크닉")
_INDOOR_KEYWORDS = ("실내", "전시", "미술관", "박물관", "영화", "카페", "볼링", "공연", "몰")

LARGE_PARTY = 5  # 이 인원부터는 단체석 여부가 중요해진다
_LARGE_PARTY_KEYWORDS = ("룸", "단체", "홀", "연회", "코스")
_SMALL_PARTY_KEYWORDS = ("카운터", "조용", "아담")


def _party_keywords(party_size: int | None) -> tuple[str, ...]:
    if party_size is None:
        return ()
    if party_size >= LARGE_PARTY:
        return _LARGE_PARTY_KEYWORDS
    if party_size <= 2:
        return _SMALL_PARTY_KEYWORDS
    return ()


# 동행유형별 선호 특성(이름/카테고리에 등장 시 가점)
_COMPANION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "데이트": ("분위기", "뷰", "루프탑", "야경", "감성"),
    "회식": ("룸", "단체", "고기", "포차", "호프"),
    "가족": ("한정식", "좌식", "룸", "브런치", "공원"),
    "친구": ("가성비", "핫플", "브런치"),
    "혼자": ("바", "카운터", "조용"),
}


SLOT_HOURS = 2  # 한 칸(방문+이동)에 대략 2시간


# ── 카테고리 시퀀스 템플릿 (B) ───────────────────────────────────
def desired_slots(constraints: PlanConstraints) -> list[str]:
    dur = constraints.duration_min or 180
    n = max(2, min(4, dur // 90))
    if constraints.stop_count:  # "2차", "세 군데" 처럼 개수를 직접 말했으면 그 값을 따른다
        n = max(1, min(4, constraints.stop_count))
        if n == 1:  # "한 곳만" — 식사 시간대면 식당, 아니면 카페 한 칸
            hour = constraints.start_time.hour if constraints.start_time else 12
            return ["meal" if _is_mealtime(hour) else "cafe"]
    evening = constraints.start_time is not None and constraints.start_time.hour >= 18
    comp = constraints.companion

    # 회식: 식사+술 중심 / 데이트: 활동·분위기 포함 / 가족: 술 배제·활동 위주
    if comp == "회식":
        slots = {2: ["meal", "bar"], 3: ["meal", "cafe", "bar"], 4: ["meal", "cafe", "bar", "bar"]}[n]
        return _shift_meal_to_mealtime(slots, constraints.start_time)
    if comp == "가족":
        slots = {
            2: ["meal", "cafe"],
            3: ["meal", "activity", "cafe"],
            4: ["meal", "activity", "cafe", "activity"],
        }[n]
        return _shift_meal_to_mealtime(slots, constraints.start_time)

    last = "bar" if (evening and comp != "가족") else ("activity" if comp == "데이트" else "cafe")
    base = {
        2: ["meal", "cafe" if comp == "데이트" else ("bar" if evening else "cafe")],
        3: ["meal", "cafe", last],
        4: ["meal", "activity", "cafe", last],
    }[n]
    return _shift_meal_to_mealtime(base, constraints.start_time)


# 식사 시간대(현지 관습): 점심 11~14시, 저녁 17~21시
def _is_mealtime(hour: int) -> bool:
    return 11 <= hour < 14 or 17 <= hour < 21


def _shift_meal_to_mealtime(slots: list[str], start: time | None) -> list[str]:
    """식사가 아닌 시각에 시작하면 첫 식사를 식사 시간대로 미룬다.

    예: 오전 10시 시작이면 "식사 → 카페" 대신 "카페 → 식사"(브런치 후 점심).
    한 칸에 90분을 잡고 앞에서부터 시간을 더해 식사 시간대에 가장 먼저 닿는 칸을 찾는다.
    """
    if start is None or "meal" not in slots or _is_mealtime(start.hour):
        return slots
    meal_at = slots.index("meal")
    for offset in range(1, len(slots)):
        hour = (start.hour + offset * SLOT_HOURS) % 24
        if _is_mealtime(hour):
            moved = list(slots)
            moved.pop(meal_at)
            moved.insert(offset, "meal")
            return moved
    return slots


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


def route_order_from(places: list[Place], origin: Place) -> list[Place]:
    """출발지에서 가장 가까운 곳부터 최근접 이웃으로 잇는다."""
    if len(places) <= 1:
        return places
    remaining = list(places)
    first = min(remaining, key=lambda p: _dist(origin, p))
    remaining.remove(first)
    return [first, *route_order([first, *remaining])[1:]]


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


# ── 협업 필터링 선택 (활용): 공동 채택 친화도로 슬롯 채우기 ────────
def _cf_pick(ranked: list[Place], slots: list[str]) -> list[Place]:
    """슬롯별로 이미 담긴 장소들과 공동 채택 친화도가 높은 후보를 선택.

    친화도 데이터가 없으면 랭킹 순으로 자연 복귀(콜드스타트 안전).
    """
    from app.cooccurrence import cooccurrence_store

    used: set[str] = set()
    picked: list[Place] = []
    for slot in slots:
        cands = [p for p in ranked if p.id not in used and classify(p) == slot]
        if not cands:
            cands = [p for p in ranked if p.id not in used]
        if not cands:
            continue
        anchors = [p.id for p in picked]
        # 랭킹(내림차순)을 유지하며 친화도 높은 후보 우선(안정 정렬)
        best = max(cands, key=lambda p: cooccurrence_store.affinity(p.id, anchors))
        picked.append(best)
        used.add(best.id)
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
    origin: Place | None = None,
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

    # 콜드스타트 판정(활용): 행동 신호(인기·자체별점·시간대)가 전무하면 외부 평점 폴백
    behavioral_mass = (
        sum(raw.values())
        + sum(v for v in self_ratings.values() if v is not None)
        + sum(ctx_pop.values())
    )
    cold_start = behavioral_mass <= 0.0

    ranked = sorted(
        candidates,
        key=lambda p: score_place(
            p, constraints, prefs, pop.get(p.id, 0.0), self_ratings.get(p.id),
            ctx_pop.get(p.id, 0.0), cold_start,
        ),
        reverse=True,
    )
    slots = desired_slots(constraints)

    # 후보 코스 시드 → 각각 물리 검증 후 코스 점수로 최고 선택 (D). 라벨로 선택 로깅(#15).
    seeds: list[tuple[str, list[Place]]] = []
    templated = _pick_by_template(ranked, slots)
    if templated:
        seeds.append(("template", templated))          # 1) 템플릿 순서
        seeds.append(("route", route_order(templated)))  # 2) 동선 최적화
        seeds.append(("sequence", seq_order(templated)))  # 3) 학습된 선호 순서(#7)
    cf = _cf_pick(ranked, slots)
    if cf:
        seeds.append(("cf", cf))                         # 4) 협업 필터링(공동 채택)
    if templated and origin is not None:
        seeds.append(("start", route_order_from(templated, origin)))  # 출발지 기준 동선
    seeds.append(("score", ranked[: len(slots)]))       # 5) 순수 점수 상위

    best: list[TimelineItem] = []
    best_score = float("-inf")
    best_label = ""
    for label, seed in seeds:
        timeline = await build_timeline(seed, constraints, map_service)
        s = course_score(timeline)
        if s > best_score:
            best_score, best, best_label = s, timeline, label
    # #15: 어떤 시드 전략이 채택됐는지 누적 → 목적함수 가중치 튜닝 데이터
    if best_label:
        from app.strategy import strategy_store

        strategy_store.bump(best_label)
    return best
