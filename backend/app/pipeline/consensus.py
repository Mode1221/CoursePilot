"""둘의 마음 합치기 — 두 사람의 30초 카드를 하나의 코스 조건으로.

배경: 데이트 코스 불만의 상위(계획 없는 연인·반응 없는 연인·컨디션 미고려·늘 같은 코스)는
장소가 아니라 관계의 문제다. 한 사람이 검색해 후보를 던지는 대신, 상대가 먼저 30초
카드(컨디션·땡기는 것·싫은 것·예산)에 답하고 그 답을 **눈에 보이게** 반영한다.

규칙(설명 가능해야 하므로 LLM 이 아니라 규칙이다):
- 싫은 것: **합집합** — 한 명이라도 싫으면 뺀다(거부권은 싸고 불만은 비싸다)
- 예산: **작은 값** — 부담을 느끼는 쪽 기준. 상대에게는 숫자를 보여주지 않는다
- 컨디션: **더 제약이 큰 쪽** — 피곤한 사람 기준으로 이동·장소 수를 줄인다
- 땡기는 것: **평균 내지 말고 칸을 나눈다** — 각자 최소 한 칸은 자기 취향
- 같은 칸에서 부딪히면 **지난번 양보한 쪽 우선**(공평 장부), 나머지는 그 칸 대안 1순위
- 둘 다 "아무거나": 조건 없이 플래너에 맡긴다(우리 기록이 쌓이면 그것으로)

산출물은 PlanConstraints 갱신 + 반영 이유(누구의 무엇 → 어디에)다. 반영 이유는
코스 화면의 칩("👤지은 피곤 → 도보 10분 이내")이 되며, 이게 이 기능의 아하 모먼트다.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas import PlanConstraints

# ── 카드 선택지(프론트와 공유) ──────────────────────────────────────────────
CONDITIONS = ("fresh", "normal", "tired", "hungry")
CRAVINGS = ("고기", "면", "한식", "양식", "일식", "디저트", "술 한잔", "새로운 거", "아무거나")
DISLIKES = ("웨이팅", "매운 거", "시끄러운 곳", "많이 걷기", "사람 많은 곳", "없음")
BUDGET_BANDS = (20000, 30000, 50000, 0)  # 0 = 상관없음

# 땡기는 것 → 코스 칸(슬롯)과 검색 키워드. 플래너의 _SLOT_KEYWORDS 와 어긋나지 않게 둔다.
CRAVING_SLOT: dict[str, tuple[str, str]] = {
    "고기": ("meal", "고기"),
    "면": ("meal", "면"),
    "한식": ("meal", "한식"),
    "양식": ("meal", "양식"),
    "일식": ("meal", "일식"),
    "디저트": ("cafe", "디저트"),
    "술 한잔": ("bar", "와인"),
    "새로운 거": ("activity", "전시"),
}
# 싫은 것 → 제외 키워드 또는 조건. "많이 걷기"는 키워드가 아니라 이동 제한이다.
DISLIKE_KEYWORD: dict[str, str | None] = {
    "웨이팅": "웨이팅",
    "매운 거": "매운",
    "시끄러운 곳": "시끄러운",
    "사람 많은 곳": "붐비는",
    "많이 걷기": None,
    "없음": None,
}
TIRED_MAX_TRAVEL_MIN = 10
NO_WALK_MAX_TRAVEL_MIN = 12


class ParticipantInput(BaseModel):
    """한 사람의 30초 카드. 예산은 저장하되 상대 응답에는 절대 내보내지 않는다."""

    name: str
    condition: str = "normal"  # CONDITIONS
    cravings: list[str] = Field(default_factory=list)  # CRAVINGS 중 여러 개
    dislikes: list[str] = Field(default_factory=list)  # DISLIKES 중 여러 개
    budget_band: int | None = None  # 1인 원. 0/None = 상관없음
    note: str = ""  # 자유 한마디("팝업 가보고 싶어") — 자연어 파서에 덧붙인다


class Attribution(BaseModel):
    """반영 이유 한 조각: 누구의 무엇이 어디에 반영됐는가."""

    who: str
    what: str  # 카드에서 고른 그대로("피곤해", "고기", "매운 거")
    effect: str  # 사람이 읽는 결과("도보 10분 이내로", "저녁은 고기")
    slot: str | None = None  # 특정 칸에 붙는 이유면 그 슬롯, 코스 전체면 None


class ConsensusResult(BaseModel):
    constraints: PlanConstraints
    attributions: list[Attribution]
    slot_owner: dict[str, str] = Field(default_factory=dict)  # slot → 이름(칸 나누기)
    yielded: str | None = None  # 이번에 양보한 사람(공평 장부용)
    conflict_note: str | None = None  # "저녁: 민수 고기 vs 지은 파스타 → 대안 1순위"
    summary: list[dict] = Field(default_factory=list)  # 코스 전체 요약 줄(attach 후 채워짐)


def _display_condition(cond: str) -> str:
    return {"fresh": "쌩쌩", "normal": "보통", "tired": "피곤해", "hungry": "배고플 듯"}.get(cond, cond)


def merge(
    inputs: list[ParticipantInput],
    base: PlanConstraints,
    *,
    prefer: str | None = None,
) -> ConsensusResult:
    """두 카드를 base 조건 위에 얹는다. prefer 는 공평 장부상 이번에 우선할 사람.

    base 는 시작하는 사람의 한 줄 요청(+온보딩 선호)에서 나온 조건이다. 카드는 그것을
    덮어쓰지 않고 좁힌다(예산은 더 작게, 이동은 더 짧게, 제외는 더 많이).
    """
    attributions: list[Attribution] = []
    c = base.model_copy(deep=True)

    # 1) 싫은 것: 합집합
    for p in inputs:
        for d in p.dislikes:
            kw = DISLIKE_KEYWORD.get(d, d)
            if d == "많이 걷기":
                c.max_travel_min = min(c.max_travel_min or 99, NO_WALK_MAX_TRAVEL_MIN)
                attributions.append(
                    Attribution(who=p.name, what=d, effect=f"이동 {NO_WALK_MAX_TRAVEL_MIN}분 이내로")
                )
                continue
            if kw is None:
                continue
            if kw not in c.exclude_keywords:
                c.exclude_keywords.append(kw)
            attributions.append(Attribution(who=p.name, what=d, effect=f"{d} 빼기"))

    # 2) 예산: 작은 값 (0/None 은 상관없음)
    budgets = [(p.budget_band, p.name) for p in inputs if p.budget_band]
    if budgets:
        lowest, who = min(budgets)
        if c.budget_max is None or lowest < c.budget_max:
            c.budget_max = lowest
        # 숫자는 상대에게 보이지 않는다 — effect 에 금액을 적지 않는다
        attributions.append(Attribution(who=who, what="예산", effect="예산 맞춤"))

    # 3) 땡기는 것: 칸 나누기 (평균 내지 않는다 — 각자 최소 한 칸은 자기 취향)
    slot_owner: dict[str, str] = {}
    yielded: str | None = None
    conflict_note: str | None = None
    wants: list[tuple[str, str, str, str]] = []  # (name, craving, slot, keyword)
    for p in inputs:
        for cr in p.cravings:
            if cr in CRAVING_SLOT:
                slot, kw = CRAVING_SLOT[cr]
                wants.append((p.name, cr, slot, kw))
    order = sorted({w[0] for w in wants}, key=lambda n: (n != prefer, n))
    for name in order:
        for who, cr, slot, kw in wants:
            if who != name:
                continue
            if slot in slot_owner and slot_owner[slot] != who:
                if slot_owner[slot] == prefer or prefer is None:
                    yielded = who
                    conflict_note = f"{_slot_ko(slot)}: {slot_owner[slot]}님 취향 우선, {who}님의 {cr}는 교체 후보로"
                    if kw not in c.keywords:
                        c.keywords.append(kw)
                    continue
            slot_owner.setdefault(slot, who)
            if kw not in c.keywords:
                c.keywords.append(kw)
            attributions.append(Attribution(who=who, what=cr, effect=f"{_slot_ko(slot)} 칸", slot=slot))
            break
    for who, cr, slot, kw in wants:
        if slot in slot_owner:
            continue
        slot_owner[slot] = who
        if kw not in c.keywords:
            c.keywords.append(kw)
        attributions.append(Attribution(who=who, what=cr, effect=f"{_slot_ko(slot)} 칸", slot=slot))

    # 4) 반드시 들어갈 칸 + 칸별 검색어
    required = list(dict.fromkeys(slot_owner))
    hungry = [p for p in inputs if p.condition == "hungry"]
    if hungry:
        required = ["meal", *[s_ for s_ in required if s_ != "meal"]]
        c.lead_slot = "meal"
        attributions.append(Attribution(who=hungry[0].name, what="배고플 듯", effect="첫 칸은 밥부터", slot="meal"))
    c.required_slots = required
    c.slot_queries = [list(q) for q in dict.fromkeys((slot, kw) for _, _, slot, kw in wants)]

    # 5) 칸 수 — 취향 칸은 모두 들어가야 한다. 피곤하면 한 곳 줄이되 취향 칸 아래로는 안 내린다.
    n_base = c.stop_count or max(2, min(6, (c.duration_min or 180) // 90))
    n = max(n_base, len(required))
    tired = [p for p in inputs if p.condition == "tired"]
    if tired:
        c.max_travel_min = min(c.max_travel_min or 99, TIRED_MAX_TRAVEL_MIN)
        fewer = max(2, len(required), n - 1)
        effect = f"이동 {TIRED_MAX_TRAVEL_MIN}분 이내" + (", 한 곳 덜" if fewer < n else "")
        n = fewer
        attributions.append(Attribution(who=tired[0].name, what="피곤해", effect=effect))
    if n != n_base or base.stop_count:
        c.stop_count = n

    # 5) 자유 한마디는 키워드로 덧붙인다(자연어 파서를 여기서 돌리지 않는다 — 호출부가 text 에 합친다)
    return ConsensusResult(
        constraints=c,
        attributions=attributions,
        slot_owner=slot_owner,
        yielded=yielded,
        conflict_note=conflict_note,
    )


def _slot_ko(slot: str) -> str:
    return {"meal": "식사", "cafe": "카페", "bar": "술", "activity": "할거리"}.get(slot, slot)


def notes_text(inputs: list[ParticipantInput]) -> str:
    """자유 한마디들을 자연어 요청 뒤에 이어 붙일 문자열."""
    return " ".join(p.note.strip() for p in inputs if p.note and p.note.strip())


# 칩이 "반영했다"고 말하려면 실제 고른 장소가 그 취향에 맞아야 한다(맞지 않으면 말하지 않는다).
CRAVING_MATCH: dict[str, tuple[str, ...]] = {
    "고기": ("고기", "구이", "갈비", "삼겹", "스테이크", "바베큐", "곱창", "막창", "육류", "정육"),
    "면": ("면", "국수", "라멘", "우동", "파스타", "쌀국수", "냉면", "소바"),
    "한식": ("한식", "한정식", "백반", "국밥", "찌개", "갈비", "보쌈"),
    "양식": ("양식", "이탈리", "파스타", "스테이크", "프렌치", "피자", "브런치", "레스토랑"),
    "일식": ("일식", "초밥", "스시", "라멘", "돈까스", "이자카야", "우동", "오마카세"),
    "디저트": ("디저트", "베이커리", "케이크", "빵", "카페", "제과", "도넛"),
}
SLOT_ONLY = {"술 한잔": "bar", "새로운 거": "activity"}  # 슬롯이 맞으면 반영으로 본다


def place_matches(place, attr: dict) -> bool:
    """이 장소가 반영 이유(취향)를 실제로 만족하는가."""
    from app.pipeline.planner import classify

    what = attr.get("what", "")
    slot = attr.get("slot")
    if what == "배고플 듯":
        return classify(place) == "meal"
    if what in SLOT_ONLY:
        return classify(place) == SLOT_ONLY[what]
    words = CRAVING_MATCH.get(what)
    if words is None:
        return slot is None or classify(place) == slot
    hay = f"{place.category or ''} {place.name}"
    return any(w in hay for w in words)


def _summary(attrs: list[dict], timeline) -> list[dict]:
    """코스 전체에 해당하는 이유를 한 줄 요약으로. 확인 가능한 것은 실제로 지켜졌을 때만."""
    out: list[dict] = []
    legs = [it.travel_to_next.duration_min for it in timeline if it.travel_to_next]
    for a in attrs:
        effect = a.get("effect", "")
        if "이동" in effect and legs:
            limit = next((int(x) for x in effect.replace("분", " ").split() if x.isdigit()), None)
            if limit is not None and max(legs) > limit:
                # 지키지 못한 부분은 말하지 않는다. 다른 부분("한 곳 덜")은 지켰으면 남긴다.
                rest = [part for part in effect.split(", ") if "이동" not in part]
                if not rest:
                    continue
                a = {**a, "effect": ", ".join(rest)}
        if a.get("what") == "예산":
            prices = [it.place.price for it in timeline]
            if any(p is None for p in prices) or not prices:
                pass  # 가격을 모르면 "맞춤"을 단정하지 않되, 조건으로는 걸었으니 남긴다
        out.append(a)
    return out


def apply_attributions(timeline, all_attrs: list[dict]) -> tuple[list[dict], list[dict]]:
    """칸에는 그 칸이 실제로 만족하는 취향만, 코스 전체 이유는 요약으로.

    반환: (summary, unmet) — unmet 은 맞는 곳을 못 찾은 취향(요약 줄에 솔직하게 표시).
    """
    global_attrs = [a for a in all_attrs if not a.get("slot")]
    slot_attrs = [a for a in all_attrs if a.get("slot")]
    for item in timeline:
        item.attributions = []
    unmet: list[dict] = []
    for a in slot_attrs:
        target = next((it for it in timeline if place_matches(it.place, a)), None)
        if target is None:
            unmet.append({**a, "effect": "맞는 곳을 못 찾았어요 · 교체에서 골라보세요"})
            continue
        target.attributions.append(a)
    return _summary(global_attrs, timeline) + unmet, unmet


def attach_attributions(timeline, result: ConsensusResult) -> list[dict]:
    """합친 직후 한 번. 요약 줄을 돌려준다(호출부가 course.together.summary 에 저장)."""
    all_attrs = [a.model_dump() for a in result.attributions]
    summary, _ = apply_attributions(timeline, all_attrs)
    return summary


def refresh_course_attributions(course) -> None:
    """교체·순서 변경·추가·삭제 뒤에 칩을 다시 붙인다(바뀐 장소가 취향에 맞는지 다시 확인)."""
    t = getattr(course, "together", None)
    if t is None or not t.attributions:
        return
    t.summary, _ = apply_attributions(course.items, t.attributions)
