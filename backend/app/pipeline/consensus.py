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

    # 3) 컨디션: 더 제약이 큰 쪽
    tired = [p for p in inputs if p.condition == "tired"]
    hungry = [p for p in inputs if p.condition == "hungry"]
    if tired:
        p = tired[0]
        c.max_travel_min = min(c.max_travel_min or 99, TIRED_MAX_TRAVEL_MIN)
        if c.stop_count:
            c.stop_count = max(2, c.stop_count - 1)
        elif c.duration_min and c.duration_min > 180:
            c.duration_min = max(120, c.duration_min - 60)  # 칸 수를 하나 줄이는 효과
        if "앉아서" not in c.keywords:
            c.keywords.append("앉아서")
        attributions.append(
            Attribution(who=p.name, what="피곤해", effect=f"이동 {TIRED_MAX_TRAVEL_MIN}분 이내, 한 곳 덜")
        )
    if hungry:
        p = hungry[0]
        # 첫 칸을 식사로: 플래너의 keyword_slot 이 첫 키워드로 슬롯을 잡는다
        c.keywords.insert(0, "식당")
        attributions.append(Attribution(who=p.name, what="배고플 듯", effect="첫 칸은 밥부터", slot="meal"))

    # 4) 땡기는 것: 칸 나누기
    slot_owner: dict[str, str] = {}
    yielded: str | None = None
    conflict_note: str | None = None
    wants: list[tuple[str, str, str, str]] = []  # (name, craving, slot, keyword)
    for p in inputs:
        for cr in p.cravings:
            if cr in CRAVING_SLOT:
                slot, kw = CRAVING_SLOT[cr]
                wants.append((p.name, cr, slot, kw))
    # 각자 최소 한 칸 — 우선권 있는 사람부터, 그다음 아직 칸이 없는 사람
    order = sorted({w[0] for w in wants}, key=lambda n: (n != prefer, n))
    for name in order:
        for who, cr, slot, kw in wants:
            if who != name:
                continue
            if slot in slot_owner and slot_owner[slot] != who:
                # 같은 칸 충돌: 이미 주인이 있으면 이 사람이 양보 → 대안 1순위로
                if slot_owner[slot] == prefer or prefer is None:
                    yielded = who
                    conflict_note = f"{slot}: {slot_owner[slot]}가 우선, {who}의 {cr}는 대안 1순위"
                    if kw not in c.keywords:
                        c.keywords.append(kw)  # 대안 후보가 검색에 잡히도록 키워드는 남긴다
                    continue
            slot_owner.setdefault(slot, who)
            if kw not in c.keywords:
                c.keywords.append(kw)
            attributions.append(Attribution(who=who, what=cr, effect=f"{_slot_ko(slot)} 칸", slot=slot))
            break  # 이 사람의 첫 칸 확보
    # 남은 취향은 슬롯 주인이 비어 있을 때만 채운다
    for who, cr, slot, kw in wants:
        if slot in slot_owner:
            continue
        slot_owner[slot] = who
        if kw not in c.keywords:
            c.keywords.append(kw)
        attributions.append(Attribution(who=who, what=cr, effect=f"{_slot_ko(slot)} 칸", slot=slot))

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


def attach_attributions(timeline, result: ConsensusResult) -> None:
    """만든 코스의 칸마다 반영 이유를 붙인다(코스 전체 이유는 모든 칸에, 칸 이유는 그 칸에).

    슬롯 판정은 플래너의 classify 를 쓴다 — 표시와 배정 기준이 어긋나지 않게.
    """
    from app.pipeline.planner import classify

    global_attrs = [a for a in result.attributions if a.slot is None]
    by_slot: dict[str, list[Attribution]] = {}
    for a in result.attributions:
        if a.slot:
            by_slot.setdefault(a.slot, []).append(a)
    seen_slots: set[str] = set()
    for item in timeline:
        slot = classify(item.place)
        attrs = list(global_attrs) if item is timeline[0] else []
        if slot in by_slot and slot not in seen_slots:
            attrs.extend(by_slot[slot])
            seen_slots.add(slot)
        item.attributions = [a.model_dump() for a in attrs]  # 코스 JSON 스냅샷에 그대로 실린다
