"""합의 코스 정확도 평가 — 실데이터(카카오·네이버)로 시나리오를 돌려 채점한다.

VM 에서 `python scripts/eval_consensus.py` 로 실행한다. 채점 함수는 순수 함수라 단위 테스트한다.

지표(코스 하나당):
- region_ok      : 모든 장소가 상권 중심에서 max_km 안인가(엉뚱한 동네로 가지 않았나)
- both_in_slots  : 두 사람 모두 **칸 칩**(요약 말고)에 이름이 있나 — 양쪽 반영
- craving_hit    : 배정된 취향 중 실제로 맞는 장소를 찾은 비율(= 1 - 못 찾았어요)
- unfit          : 데이트 부적합 업태(구내식당·학교 등)가 섞였나
- dislike_hit    : 싫다고 한 것(매운·웨이팅 등)이 장소 이름/분류에 드러났나
- travel_ok      : 이동 제한(피곤·많이 걷기)을 지켰나
- stops          : 칸 수, 중복 장소
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

from app.pipeline.consensus import ParticipantInput

# 싫은 것 → 장소 이름·분류에 이게 보이면 위반으로 본다(보수적: 확실한 표기만)
DISLIKE_SIGNS: dict[str, tuple[str, ...]] = {
    "매운 거": ("매운", "마라", "불닭", "떡볶이", "짬뽕", "쭈꾸미", "낙지"),
    "시끄러운 곳": ("클럽", "노래방", "헌팅", "감성주점"),
    "사람 많은 곳": (),  # 이름으로 판단 불가
    "웨이팅": (),  # 실시간 정보 없음
    "많이 걷기": (),  # travel_ok 로 본다
}


@dataclass(frozen=True)
class Scenario:
    key: str
    request: str
    region: str
    a: ParticipantInput
    b: ParticipantInput


@dataclass
class Score:
    key: str
    region: str
    stops: int = 0
    names: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    max_km: float = 0.0
    region_ok: bool = True
    both_in_slots: bool = False
    craving_total: int = 0
    craving_hit: int = 0
    unfit: list[str] = field(default_factory=list)
    dislike_hits: list[str] = field(default_factory=list)
    travel_ok: bool = True
    max_leg: int = 0
    duplicates: bool = False
    unmet: list[str] = field(default_factory=list)
    yielded: str | None = None
    error: str | None = None
    # 데이트 품질(통과 조건엔 넣지 않고 수치로 본다)
    chains: list[str] = field(default_factory=list)  # 저가 프랜차이즈
    same_slot_in_row: bool = False  # 카페 → 카페처럼 같은 성격이 연달아
    slots: list[str] = field(default_factory=list)

    def passed(self) -> bool:
        return (
            self.error is None
            and self.stops >= 2
            and self.region_ok
            and self.both_in_slots
            and not self.unfit
            and not self.dislike_hits
            and self.travel_ok
            and not self.duplicates
        )

    def as_dict(self) -> dict:
        d = asdict(self)
        d["passed"] = self.passed()
        return d


def _km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def score(scn: Scenario, timeline, summary: list[dict], constraints, center: tuple[float, float] | None,
          yielded: str | None = None, max_km: float = 2.5) -> Score:
    """생성된 코스를 채점한다(외부 호출 없음)."""
    from app.pipeline.planner import is_unfit_for_date

    s = Score(key=scn.key, region=scn.region, yielded=yielded)
    s.stops = len(timeline)
    s.names = [it.place.name for it in timeline]
    s.categories = [(it.place.category or "").split(">")[-1].strip() for it in timeline]
    ids = [it.place.id for it in timeline]
    s.duplicates = len(ids) != len(set(ids))
    if center:
        dists = [_km(center[0], center[1], it.place.lat, it.place.lng) for it in timeline]
        s.max_km = round(max(dists), 2) if dists else 0.0
        s.region_ok = s.max_km <= max_km
    slot_whos = {a["who"] for it in timeline for a in (it.attributions or [])}
    # 정말 겹칠 때 한 명이 양보하는 건 설계다 — 요약 줄에 "양보"로 드러나 있으면 반영된 것으로 본다
    yielded_whos = {a["who"] for a in summary if "양보" in a.get("effect", "")}
    craving_people = {p.name for p in (scn.a, scn.b) if p.cravings}
    s.both_in_slots = craving_people <= (slot_whos | yielded_whos) if craving_people else True
    hit = sum(1 for it in timeline for a in (it.attributions or []) if a.get("slot"))
    s.unmet = [f"{a['who']}:{a['what']}" for a in summary if "못 찾았어요" in a.get("effect", "")]
    s.craving_hit = hit
    s.craving_total = hit + len(s.unmet)
    s.unfit = [it.place.name for it in timeline if is_unfit_for_date(it.place)]
    for p in (scn.a, scn.b):
        for d in p.dislikes:
            for sign in DISLIKE_SIGNS.get(d, ()):
                for it in timeline:
                    hay = f"{it.place.name} {it.place.category or ''}"
                    if sign in hay:
                        s.dislike_hits.append(f"{p.name}:{d}→{it.place.name}")
    from app.pipeline.planner import classify, franchise_level

    s.slots = [classify(it.place) for it in timeline]
    s.same_slot_in_row = any(a == b for a, b in zip(s.slots, s.slots[1:], strict=False))
    s.chains = [it.place.name for it in timeline if franchise_level(it.place) == 2]
    legs = [it.travel_to_next.duration_min for it in timeline if it.travel_to_next]
    s.max_leg = max(legs) if legs else 0
    # 원래 바람 기준으로 잰다 — 플래너가 조건을 완화하면 결과 constraints 의 제한도 늘어나 위반이 숨는다
    wished = [10 for p in (scn.a, scn.b) if p.condition == "tired"] + [
        12 for p in (scn.a, scn.b) if "많이 걷기" in p.dislikes
    ]
    limit = min(wished) if wished else getattr(constraints, "max_travel_min", None)
    s.travel_ok = not (limit and legs and max(legs) > limit)
    return s


def default_scenarios(regions: list[str]) -> list[Scenario]:
    """상권 × 취향 조합. 겹침(식사끼리)·안 겹침·아무거나·배고픔·피곤·예산을 고루."""
    pairs = [
        ("안겹침", ParticipantInput(name="민수", cravings=["고기"], dislikes=["웨이팅"]),
         ParticipantInput(name="지은", condition="tired", cravings=["디저트", "새로운 거"], dislikes=["매운 거"])),
        ("식사겹침", ParticipantInput(name="민수", cravings=["고기"]),
         ParticipantInput(name="지은", cravings=["양식"], dislikes=["매운 거"])),
        ("술+할거리", ParticipantInput(name="민수", cravings=["술 한잔"], dislikes=["시끄러운 곳"]),
         ParticipantInput(name="지은", cravings=["새로운 거"])),
        ("아무거나", ParticipantInput(name="민수", cravings=[], dislikes=["사람 많은 곳"]),
         ParticipantInput(name="지은", cravings=["디저트"], dislikes=["매운 거"])),
        ("배고픔", ParticipantInput(name="민수", condition="hungry", cravings=["면"]),
         ParticipantInput(name="지은", cravings=["일식", "디저트"])),
        ("예산", ParticipantInput(name="민수", cravings=["한식"], budget_band=20000),
         ParticipantInput(name="지은", cravings=["디저트"], budget_band=30000, dislikes=["많이 걷기"])),
    ]
    out = []
    for region in regions:
        for key, a, b in pairs:
            out.append(Scenario(key=f"{region}/{key}", request=f"토요일 오후 3시 {region}", region=region, a=a, b=b))
    return out


def summarize(scores: list[Score]) -> dict:
    n = len(scores) or 1
    total_c = sum(s.craving_total for s in scores) or 1
    return {
        "runs": len(scores),
        "pass_rate": round(sum(s.passed() for s in scores) / n, 3),
        "region_ok": round(sum(s.region_ok for s in scores) / n, 3),
        "both_in_slots": round(sum(s.both_in_slots for s in scores) / n, 3),
        "craving_hit_rate": round(sum(s.craving_hit for s in scores) / total_c, 3),
        "unfit_runs": sum(bool(s.unfit) for s in scores),
        "dislike_runs": sum(bool(s.dislike_hits) for s in scores),
        "travel_violations": sum(not s.travel_ok for s in scores),
        "duplicates": sum(s.duplicates for s in scores),
        "errors": sum(s.error is not None for s in scores),
        "avg_stops": round(sum(s.stops for s in scores) / n, 2),
        # 데이트 품질
        "three_plus_stops": round(sum(s.stops >= 3 for s in scores) / n, 3),
        "same_slot_in_row_runs": sum(s.same_slot_in_row for s in scores),
        "budget_chain_runs": sum(bool(s.chains) for s in scores),
        "max_place_share_per_region": _max_share(scores),
    }


def _max_share(scores: list[Score]) -> float:
    """상권 안에서 가장 자주 나온 한 장소의 등장 비율(다양성). 1.0 이면 모든 코스에 같은 곳."""
    from collections import Counter

    worst = 0.0
    by_region: dict[str, list[Score]] = {}
    for s in scores:
        by_region.setdefault(s.region, []).append(s)
    for runs in by_region.values():
        c = Counter(n for s in runs for n in set(s.names))
        if c and runs:
            worst = max(worst, c.most_common(1)[0][1] / len(runs))
    return round(worst, 3)
