"""합치기 엔진 — 두 카드를 하나의 조건으로 만드는 규칙(표 기반)."""
from app.pipeline.consensus import (
    NO_WALK_MAX_TRAVEL_MIN,
    TIRED_MAX_TRAVEL_MIN,
    ParticipantInput,
    attach_attributions,
    merge,
)
from app.schemas import Place, PlanConstraints, TimelineItem


def _p(name, **kw):
    return ParticipantInput(name=name, **kw)


def test_싫은_것은_합집합():
    r = merge([_p("민수", dislikes=["웨이팅"]), _p("지은", dislikes=["매운 거"])], PlanConstraints())
    assert set(r.constraints.exclude_keywords) == {"웨이팅", "매운"}
    whos = {(a.who, a.what) for a in r.attributions}
    assert ("민수", "웨이팅") in whos and ("지은", "매운 거") in whos


def test_예산은_작은_값이고_숫자는_이유에_없다():
    r = merge([_p("민수", budget_band=50000), _p("지은", budget_band=30000)], PlanConstraints())
    assert r.constraints.budget_max == 30000
    budget = next(a for a in r.attributions if a.what == "예산")
    assert budget.who == "지은" and "30" not in budget.effect and "원" not in budget.effect


def test_요청에_적힌_예산이_더_작으면_그것을_지킨다():
    r = merge([_p("지은", budget_band=50000)], PlanConstraints(budget_max=20000))
    assert r.constraints.budget_max == 20000


def test_피곤한_쪽_기준으로_이동과_칸_수():
    r = merge([_p("민수"), _p("지은", condition="tired")], PlanConstraints(stop_count=4))
    assert r.constraints.max_travel_min == TIRED_MAX_TRAVEL_MIN
    assert r.constraints.stop_count == 3
    assert any(a.who == "지은" and a.what == "피곤해" for a in r.attributions)


def test_많이_걷기_싫으면_이동_제한():
    r = merge([_p("지은", dislikes=["많이 걷기"])], PlanConstraints())
    assert r.constraints.max_travel_min == NO_WALK_MAX_TRAVEL_MIN
    assert "많이 걷기" not in r.constraints.exclude_keywords


def test_배고프면_첫_칸은_식사():
    r = merge([_p("민수", condition="hungry")], PlanConstraints(keywords=["조용한"]))
    assert r.constraints.keywords[0] == "식당"
    assert any(a.slot == "meal" and a.what == "배고플 듯" for a in r.attributions)


def test_땡기는_것은_칸을_나눠_각자_한_칸():
    r = merge([_p("민수", cravings=["고기"]), _p("지은", cravings=["디저트"])], PlanConstraints())
    assert r.slot_owner == {"meal": "민수", "cafe": "지은"}
    assert r.yielded is None
    assert {a.slot for a in r.attributions} == {"meal", "cafe"}


def test_같은_칸_충돌은_우선권_없는_쪽이_양보():
    r = merge([_p("민수", cravings=["고기"]), _p("지은", cravings=["양식"])], PlanConstraints(), prefer="지은")
    assert r.slot_owner["meal"] == "지은"
    assert r.yielded == "민수"
    assert "고기" in r.constraints.keywords  # 대안 후보가 검색되도록 키워드는 남긴다
    assert r.conflict_note and "민수" in r.conflict_note


def test_둘_다_아무거나면_조건을_더하지_않는다():
    base = PlanConstraints(region="성수")
    r = merge([_p("민수", cravings=["아무거나"]), _p("지은")], base)
    assert r.constraints.keywords == [] and r.constraints.exclude_keywords == []
    assert r.slot_owner == {} and r.attributions == []


def test_base_조건은_덮어쓰지_않고_좁힌다():
    base = PlanConstraints(region="성수", keywords=["조용한"], max_travel_min=20)
    r = merge([_p("지은", condition="tired", cravings=["디저트"])], base)
    assert r.constraints.region == "성수" and "조용한" in r.constraints.keywords
    assert r.constraints.max_travel_min == TIRED_MAX_TRAVEL_MIN
    assert base.keywords == ["조용한"]  # 원본 불변


def test_반영_이유를_칸에_붙인다():
    r = merge([_p("민수", cravings=["고기"], dislikes=["웨이팅"]), _p("지은", cravings=["디저트"])], PlanConstraints())
    items = [
        TimelineItem(place=Place(id="c", name="카페", category="카페", lat=0, lng=0)),
        TimelineItem(place=Place(id="m", name="고깃집", category="음식점 > 고기", lat=0, lng=0)),
    ]
    attach_attributions(items, r)
    cafe, meal = items
    assert any(a["who"] == "지은" and a["slot"] == "cafe" for a in cafe.attributions)
    assert any(a["who"] == "민수" and a["slot"] == "meal" for a in meal.attributions)
    # 코스 전체 이유(웨이팅 빼기)는 첫 칸에 한 번만
    assert any(a["what"] == "웨이팅" for a in cafe.attributions)
    assert not any(a["what"] == "웨이팅" for a in meal.attributions)
