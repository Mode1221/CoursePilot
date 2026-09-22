"""정확도 평가 채점 함수(순수 함수)."""
from app.evaluation.consensus_eval import Scenario, default_scenarios, score, summarize
from app.pipeline.consensus import ParticipantInput
from app.schemas import Place, PlanConstraints, Route, TimelineItem, TravelMode


def _item(pid, name, cat, lat=37.5445, lng=127.0557, attrs=None, leg=None):
    it = TimelineItem(place=Place(id=pid, name=name, category=cat, lat=lat, lng=lng))
    it.attributions = attrs or []
    if leg:
        it.travel_to_next = Route(from_place_id=pid, to_place_id="x", mode=TravelMode.WALK, duration_min=leg, distance_m=500)
    return it


SCN = Scenario(
    key="성수/t", request="토요일 3시 성수", region="성수",
    a=ParticipantInput(name="민수", cravings=["고기"]),
    b=ParticipantInput(name="지은", cravings=["디저트"], dislikes=["매운 거"]),
)
CENTER = (37.5445, 127.0557)


def test_두_사람_모두_칸에_있으면_통과():
    tl = [
        _item("1", "성수갈비", "음식점 > 고기", attrs=[{"who": "민수", "what": "고기", "slot": "meal"}], leg=8),
        _item("2", "케이크집", "카페 > 디저트", attrs=[{"who": "지은", "what": "디저트", "slot": "cafe"}]),
    ]
    s = score(SCN, tl, [], PlanConstraints(max_travel_min=10), CENTER)
    assert s.passed() and s.craving_hit == 2 and s.craving_total == 2


def test_지역_이탈과_한쪽_누락과_싫은_것을_잡는다():
    tl = [
        _item("1", "마라탕집", "음식점 > 중식", lat=37.64, lng=126.83, attrs=[{"who": "민수", "what": "고기", "slot": "meal"}], leg=25),
        _item("2", "카페", "카페"),
    ]
    summary = [{"who": "지은", "what": "디저트", "effect": "맞는 곳을 못 찾았어요 · 교체에서 골라보세요"}]
    s = score(SCN, tl, summary, PlanConstraints(max_travel_min=10), CENTER)
    assert not s.region_ok and s.max_km > 2.5
    assert not s.both_in_slots
    assert s.dislike_hits and not s.travel_ok
    assert s.unmet == ["지은:디저트"] and s.craving_total == 2
    assert not s.passed()


def test_부적합_업태와_중복():
    tl = [_item("1", "한돌푸드", "음식점 > 구내식당"), _item("1", "한돌푸드", "음식점 > 구내식당")]
    s = score(SCN, tl, [], PlanConstraints(), CENTER)
    assert s.unfit and s.duplicates


def test_시나리오와_요약():
    scns = default_scenarios(["성수", "홍대"])
    assert len(scns) == 12 and scns[0].request.endswith("성수")
    tl = [_item("1", "a", "카페", attrs=[{"who": "민수", "what": "고기", "slot": "meal"}, {"who": "지은", "what": "디저트", "slot": "cafe"}]), _item("2", "b", "카페")]
    sm = summarize([score(SCN, tl, [], PlanConstraints(), CENTER)])
    assert sm["runs"] == 1 and sm["pass_rate"] == 1.0


def test_겹쳐서_양보가_요약에_보이면_반영된_것으로_본다():
    tl = [_item("1", "파스타", "음식점 > 양식", attrs=[{"who": "지은", "what": "양식", "slot": "meal"}]), _item("2", "카페", "카페")]
    summary = [{"who": "민수", "what": "고기", "effect": "이번엔 양보 · 다음엔 먼저, 교체에서 골라볼 수 있어요"}]
    scn = Scenario(key="t", request="x", region="성수", a=ParticipantInput(name="민수", cravings=["고기"]), b=ParticipantInput(name="지은", cravings=["양식"]))
    assert score(scn, tl, summary, PlanConstraints(), CENTER).both_in_slots
