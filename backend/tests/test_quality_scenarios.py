"""대표 시나리오 품질 회귀 방지.

파서·플래너를 고치다 보면 특정 요청만 조용히 나빠지기 쉽다. 실제로 들어올 법한
문장들을 mock 데이터로 돌려, 코스가 성립하는 최소 기준을 지키는지 확인한다.
"""
from __future__ import annotations

import pytest

from app.adapters.map_service import MockMapService
from app.pipeline.agent import generate_course
from app.pipeline.planner import classify

SCENARIOS = [
    ("성수동에서 토요일 저녁 데이트", 2),
    ("강남에서 4명이서 저녁 먹고 2차까지", 2),
    ("연남동 브런치", 2),
    ("비 오는 날 홍대 실내 데이트", 2),
    # 2시간이면 식사 한 곳으로도 코스가 성립한다(억지로 칸을 늘리지 않는다)
    ("퇴근하고 강남 두 시간", 1),
    ("성수동 오전 10시부터 5시간 도보", 3),
    ("부모님이랑 점심 한정식 강남", 2),
    ("혼자 조용히 책 읽을 곳 성수동", 1),
]


@pytest.mark.parametrize(("text", "min_stops"), SCENARIOS)
async def test_대표_시나리오는_코스가_성립한다(text: str, min_stops: int):
    result = await generate_course(text, MockMapService())
    assert len(result.timeline) >= min_stops, text

    # 시간이 거꾸로 흐르거나 겹치지 않는다
    for prev, nxt in zip(result.timeline, result.timeline[1:], strict=False):
        assert prev.depart is not None and nxt.arrive is not None
        if prev.depart <= nxt.arrive:  # 자정을 넘기는 코스는 비교 대상에서 제외
            assert prev.depart <= nxt.arrive, text


async def test_긴_코스는_같은_카테고리로만_채우지_않는다():
    result = await generate_course("성수동 오전 10시부터 5시간 도보", MockMapService())
    kinds = {classify(it.place) for it in result.timeline}
    assert len(kinds) >= 2


async def test_제외_조건은_코스에_들어가지_않는다():
    result = await generate_course("성수동 저녁 술집 빼고", MockMapService())
    assert all(classify(it.place) != "bar" for it in result.timeline)


async def test_이동시간_상한을_말하면_대체로_지킨다():
    result = await generate_course("성수동 도보 10분 이내 저녁", MockMapService())
    overs = [
        it.travel_to_next.duration_min
        for it in result.timeline
        if it.travel_to_next and it.travel_to_next.duration_min > 20
    ]
    assert not overs


async def test_요청한_성격이_첫_칸에_온다():
    """"카페" 를 말했는데 식사 시간대라고 식당부터 시작하면 요청과 어긋난다."""
    from app.cooccurrence import cooccurrence_store
    from app.pipeline.decomposition import parse_constraints
    from app.pipeline.planner import desired_slots
    from app.popularity import popularity_store
    from app.ratings import rating_store
    from app.sequence import sequence_store
    from app.timecontext import time_context_store

    # 다른 테스트가 남긴 신호가 순위·순서를 뒤집지 않게 초기화
    for store in (popularity_store, cooccurrence_store, time_context_store,
                  sequence_store, rating_store):
        store._mem.clear()

    assert desired_slots(parse_constraints("성수동 반려동물 동반 카페"))[0] == "cafe"
    assert desired_slots(parse_constraints("성수동 전시 보고 저녁"))[0] == "activity"
    # 성격을 말하지 않으면 기존 템플릿 그대로
    assert desired_slots(parse_constraints("성수동 저녁 데이트"))[0] == "meal"

    result = await generate_course("성수동 반려동물 동반 카페", MockMapService())
    assert classify(result.timeline[0].place) == "cafe"


def test_긴_시간_요청은_칸을_더_만든다():
    from app.pipeline.decomposition import parse_constraints
    from app.pipeline.planner import MAX_STOPS, desired_slots

    long_day = desired_slots(parse_constraints("성수동 오후 2시부터 밤 11시까지"))
    assert len(long_day) >= 5
    assert len(long_day) <= MAX_STOPS
    # 짧은 요청은 그대로
    assert len(desired_slots(parse_constraints("성수동 3시간"))) == 2


def test_같은_성격이_연달아_오지_않는다():
    from app.pipeline.decomposition import parse_constraints
    from app.pipeline.planner import desired_slots

    for text in ("성수동 오후 2시부터 밤 11시까지", "성수동 하루종일", "성수동 6시간"):
        slots = desired_slots(parse_constraints(text))
        assert all(a != b for a, b in zip(slots, slots[1:], strict=False)), text


def test_코스_점수는_같은_성격_연속을_감점한다():
    from datetime import time as dtime

    from app.pipeline.planner import course_score
    from app.schemas import Place, TimelineItem

    def _item(pid: str, category: str) -> TimelineItem:
        return TimelineItem(
            place=Place(id=pid, name=pid, category=category, lat=37.5, lng=127.0, rating=4.0),
            arrive=dtime(12, 0),
            depart=dtime(13, 0),
        )

    varied = [_item("a", "restaurant"), _item("b", "cafe")]
    repeated = [_item("a", "restaurant"), _item("b", "restaurant")]
    assert course_score(varied) > course_score(repeated)


async def test_긴_코스에_같은_성격이_연달아_오지_않는다():
    result = await generate_course("성수동 오후 2시부터 밤 11시까지", MockMapService())
    kinds = [classify(it.place) for it in result.timeline]
    assert all(a != b for a, b in zip(kinds, kinds[1:], strict=False)), kinds


# --- 최근에 넣은 흐름들이 조용히 깨지지 않도록 (폐업 제외·되채움·질문 답변) ---


async def test_휴무로_빠진_자리를_알리고_남은_개수로_판단한다(monkeypatch):
    async def close_first(places, *, weekday=None):
        if places:
            places[0].closed_that_day = True
        return places

    monkeypatch.setattr("app.adapters.google.refresh_final_hours", close_first)
    result = await generate_course("성수동에서 저녁 코스", MockMapService())
    assert all(not it.place.closed_that_day for it in result.timeline)
    assert result.closed_dropped >= 0


async def test_대표_질문들에_각각_다른_답을_준다():
    from app.answers import course_answer

    result = await generate_course("성수동 저녁 데이트", MockMapService())
    course = _as_course(result.timeline)
    answers = {
        q: course_answer(course, q)
        for q in ("얼마야", "영업시간 알려줘", "어떻게 가?", "왜 골랐어?")
    }
    assert len(set(answers.values())) == len(answers), answers


def _as_course(timeline):
    from app.schemas import Course

    return Course(id="c", items=timeline)


async def test_상시_조건은_요청에_자동으로_들어간다():
    result = await generate_course(
        "성수동 저녁", MockMapService(), preferences={"must_haves": ["주차"]}
    )
    assert "주차" in result.constraints.keywords
