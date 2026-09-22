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
    tired = next(a for a in r.attributions if a.who == "지은" and a.what == "피곤해")
    assert "한 곳 덜" in tired.effect


def test_피곤해도_취향_칸_아래로는_줄이지_않고_그렇다면_한_곳_덜이라고_말하지_않는다():
    r = merge(
        [_p("민수", cravings=["고기"]), _p("지은", condition="tired", cravings=["디저트"])],
        PlanConstraints(duration_min=180),
    )
    assert (r.constraints.stop_count or 2) == 2 and set(r.constraints.required_slots) == {"meal", "cafe"}
    tired = next(a for a in r.attributions if a.what == "피곤해")
    assert "한 곳 덜" not in tired.effect


def test_취향마다_칸별_검색어를_만든다():
    r = merge([_p("민수", cravings=["고기"]), _p("지은", cravings=["새로운 거", "디저트"])], PlanConstraints())
    assert ["meal", "고기"] in r.constraints.slot_queries
    assert ["activity", "전시"] in r.constraints.slot_queries
    assert "앉아서" not in r.constraints.keywords


def test_많이_걷기_싫으면_이동_제한():
    r = merge([_p("지은", dislikes=["많이 걷기"])], PlanConstraints())
    assert r.constraints.max_travel_min == NO_WALK_MAX_TRAVEL_MIN
    assert "많이 걷기" not in r.constraints.exclude_keywords


def test_배고프면_첫_칸은_식사():
    r = merge([_p("민수", condition="hungry")], PlanConstraints(keywords=["조용한"]))
    assert r.constraints.lead_slot == "meal" and r.constraints.required_slots[0] == "meal"
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
    summary = attach_attributions(items, r)
    cafe, meal = items
    assert any(a["who"] == "지은" and a["slot"] == "cafe" for a in cafe.attributions)
    assert any(a["who"] == "민수" and a["slot"] == "meal" for a in meal.attributions)
    # 코스 전체 이유(웨이팅 빼기)는 칸이 아니라 요약 줄로
    assert any(a["what"] == "웨이팅" for a in summary)
    assert not any(a["what"] == "웨이팅" for it in items for a in it.attributions)


# ── 정직한 칩 / 요약 / 편집 후 재부착 ─────────────────────────────────────
def test_취향에_맞지_않는_장소에는_칩을_붙이지_않고_요약에_솔직하게():
    r = merge([_p("민수", cravings=["고기"])], PlanConstraints())
    items = [TimelineItem(place=Place(id="m", name="한돌푸드", category="음식점 > 구내식당", lat=0, lng=0))]
    summary = attach_attributions(items, r)
    assert items[0].attributions == []
    unmet = [a for a in summary if a["what"] == "고기"]
    assert unmet and "못 찾았어요" in unmet[0]["effect"]


def test_코스_전체_이유는_칸이_아니라_요약으로():
    r = merge([_p("민수", dislikes=["웨이팅"]), _p("지은", budget_band=30000)], PlanConstraints())
    items = [TimelineItem(place=Place(id="c", name="카페", category="카페", lat=0, lng=0))]
    summary = attach_attributions(items, r)
    assert items[0].attributions == []
    assert {a["what"] for a in summary} == {"웨이팅", "예산"}


def test_이동_제한을_지키지_못했으면_요약에서_말하지_않는다():
    from app.schemas import Route, TravelMode

    r = merge([_p("지은", condition="tired")], PlanConstraints(stop_count=3))
    a = Place(id="a", name="A", category="카페", lat=0, lng=0)
    b = Place(id="b", name="B", category="카페", lat=0, lng=0)
    items = [
        TimelineItem(place=a, travel_to_next=Route(from_place_id="a", to_place_id="b", mode=TravelMode.WALK, duration_min=25, distance_m=2000)),
        TimelineItem(place=b),
    ]
    summary = attach_attributions(items, r)
    assert not any("이동" in s["effect"] for s in summary)
    assert any(s["what"] == "피곤해" and s["effect"] == "한 곳 덜" for s in summary)


def test_교체하면_새_장소_기준으로_칩을_다시_붙인다():
    from app.pipeline.consensus import refresh_course_attributions
    from app.schemas import Course, TogetherState

    r = merge([_p("민수", cravings=["고기"])], PlanConstraints())
    course = Course(id="x", together=TogetherState(token="t", request_text="성수"))
    course.together.attributions = [a.model_dump() for a in r.attributions]
    course.items = [TimelineItem(place=Place(id="1", name="구내식당", category="구내식당", lat=0, lng=0))]
    refresh_course_attributions(course)
    assert course.items[0].attributions == []
    course.items = [TimelineItem(place=Place(id="2", name="성수 갈비", category="음식점 > 고기", lat=0, lng=0))]
    refresh_course_attributions(course)
    assert course.items[0].attributions and course.items[0].attributions[0]["what"] == "고기"
    assert not any(s["what"] == "고기" for s in course.together.summary)


def test_구내식당_학교는_데이트_후보에서_빼되_이름에_대학교가_든_문화시설은_남긴다():
    from app.pipeline.planner import is_unfit_for_date

    assert is_unfit_for_date(Place(id="1", name="한돌푸드", category="음식점 > 구내식당", lat=0, lng=0))
    assert is_unfit_for_date(Place(id="3", name="홍익대학교 서울캠퍼스", category="교육,학문 > 학교 > 대학교", lat=0, lng=0))
    assert not is_unfit_for_date(Place(id="4", name="홍익대학교 박물관", category="문화,예술 > 문화시설 > 박물관", lat=0, lng=0))
    assert not is_unfit_for_date(Place(id="2", name="성수 갈비", category="음식점 > 고기", lat=0, lng=0))


def test_합의_코스는_취향_칸이_반드시_들어가고_배고프면_밥이_먼저():
    from app.pipeline.planner import desired_slots

    c = PlanConstraints(duration_min=180, companion="데이트", required_slots=["activity", "meal"])
    slots = desired_slots(c)
    assert "activity" in slots and "meal" in slots
    c2 = PlanConstraints(duration_min=270, required_slots=["meal", "cafe"], lead_slot="meal")
    assert desired_slots(c2)[0] == "meal"


async def test_합의_코스는_칸마다_따로_검색한다():
    from app.pipeline.agent import _slot_search

    calls = []

    class _Svc:
        async def search_places(self, region, keywords, limit=10):
            calls.append(tuple(keywords))
            return [Place(id=f"{region}-{'-'.join(keywords)}-{i}", name="x", lat=0, lng=0) for i in range(2)]

    c = PlanConstraints(region="홍대", required_slots=["meal", "activity"], slot_queries=[["meal", "고기"], ["activity", "전시"]], duration_min=180)
    found = await _slot_search(c, _Svc(), "홍대")
    assert ("고기",) in calls and ("전시",) in calls
    assert all(len(k) <= 1 for k in calls)  # "고기 전시" 같은 합친 질의는 없다
    assert found


def test_공개_직렬화에는_카드_원문과_토큰이_없다():
    from app.schemas import Course, TogetherState

    c = Course(id="x", together=TogetherState(token="secret", request_text="성수", inputs={"지은": {"budget_band": 30000}}))
    public = c.model_dump(mode="json")["together"]
    assert "token" not in public and "inputs" not in public and public["submitted"] == ["지은"]
    stored = c.model_dump(mode="json", context={"storage": True})["together"]
    assert stored["token"] == "secret" and stored["inputs"]["지은"]["budget_band"] == 30000


# ── 양쪽 반영(공평) ─────────────────────────────────────────────────────
def test_겹치지_않는_칸부터_나눠_둘_다_한_칸씩():
    # 지은은 양식·와인, 민수는 고기 — 식사 칸이 겹치지만 지은에게 술 칸을 주면 아무도 양보하지 않는다
    r = merge([_p("민수", cravings=["고기"]), _p("지은", cravings=["양식", "술 한잔"])], PlanConstraints())
    assert r.slot_owner["meal"] == "민수" and r.slot_owner["bar"] == "지은"
    assert r.yielded is None
    assert ["meal", "고기"] in r.constraints.slot_focus and ["bar", "술 한잔"] in r.constraints.slot_focus


def test_정말_겹치면_우선권으로_가르고_양보한_취향도_요약에_보인다():
    r = merge([_p("민수", cravings=["고기"]), _p("지은", cravings=["양식"])], PlanConstraints(), prefer="지은")
    assert r.slot_owner["meal"] == "지은" and r.yielded == "민수"
    assert any(a.who == "민수" and a.what == "고기" and "양보" in a.effect and a.slot is None for a in r.attributions)


def test_칸_주인의_취향으로_후보를_좁힌다():
    from app.pipeline.planner import _focus_slots

    meat = Place(id="m", name="갈비", category="음식점 > 한식 > 육류,고기", lat=0, lng=0)
    pasta = Place(id="p", name="파스타", category="음식점 > 양식 > 이탈리안", lat=0, lng=0)
    cafe = Place(id="c", name="카페", category="음식점 > 카페", lat=0, lng=0)
    out = _focus_slots([meat, pasta, cafe], PlanConstraints(slot_focus=[["meal", "양식"]]))
    assert {p.id for p in out} == {"p", "c"}
    # 맞는 곳이 없으면 거르지 않는다
    out = _focus_slots([meat, cafe], PlanConstraints(slot_focus=[["meal", "양식"]]))
    assert {p.id for p in out} == {"m", "c"}


def test_처음엔_물어본_상대가_우선():
    from app.schemas import TogetherState
    from app.together_api import _prefer

    assert _prefer(TogetherState(token="t", request_text="x", owner_name="민수", partner_name="지은")) == "지은"
    assert _prefer(TogetherState(token="t", request_text="x", partner_name="지은", yielded="민수")) == "민수"
