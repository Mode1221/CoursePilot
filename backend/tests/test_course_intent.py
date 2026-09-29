"""혼자 만드는 코스: 문장 순서대로 칸, 칸별 검색어, 기본 3곳, 동네 밖 후보 제외, 시간 예산."""
from datetime import time

import pytest

from app.adapters.map_service import MockMapService
from app.pipeline import intent
from app.pipeline.agent import _min_valid, generate_course
from app.pipeline.decomposition import parse_constraints
from app.pipeline.planner import classify, desired_slots
from app.pipeline.stored_pool import keep_near, known_center
from app.schemas import Place


def _slots(text: str) -> list[str]:
    c = parse_constraints(text)
    intent.apply(c, text)
    return desired_slots(c)


def test_말한_순서대로_칸을_세운다():
    assert [w.slot for w in intent.wants_in_order("연남동에서 파스타 먹고 와인바 가자")] == ["meal", "bar"]
    # 마지막이 술이면 빈 칸(카페)은 그 앞에 — 와인바 뒤에 카페가 오지 않는다
    assert _slots("일요일 저녁 6시 연남동에서 파스타 먹고 와인바 가자") == ["meal", "cafe", "bar"]
    assert _slots("토요일 오후 2시 성수동에서 브런치 먹고 카페랑 소품샵 구경") == ["meal", "cafe", "activity"]
    assert _slots("일요일 오후 3시 망원동 한강 산책하고 디저트 먹기") == ["activity", "cafe", "meal"]


def test_와인바_안의_와인을_두_번_세지_않는다():
    wants = intent.wants_in_order("와인바 가고 싶어")
    assert len(wants) == 1 and wants[0].query == "와인바"


def test_빼달라고_한_건_칸으로_세우지_않는다():
    c = parse_constraints("성수동 카페 말고 술집")
    wants = intent.apply(c, "성수동 카페 말고 술집")
    assert "cafe" not in [w.slot for w in wants]


def test_칸별_검색어와_초점():
    c = parse_constraints("연남동 파스타 먹고 와인바")
    intent.apply(c, "연남동 파스타 먹고 와인바")
    assert ["meal", "파스타"] in c.slot_queries and ["bar", "와인바"] in c.slot_queries
    assert ["meal", "파스타"] in c.slot_focus


def test_시간을_말하지_않으면_기본_3곳():
    assert len(desired_slots(parse_constraints("강남역 근처 저렴하게"))) == 3


def test_개수를_말했으면_그대로():
    assert _slots("을지로 고기집 가고 2차는 술집") == ["meal", "bar"]


def test_칸을_다_채우면_완화하지_않는다():
    c = parse_constraints("을지로 고기집 가고 2차는 술집")
    intent.apply(c, "을지로 고기집 가고 2차는 술집")
    assert _min_valid(c) == 2


async def test_파스타는_파스타집으로():
    class Ms(MockMapService):
        async def search_places(self, region, keywords, limit=10):
            base = await super().search_places(region, keywords, limit)
            if keywords == ["파스타"]:
                return [
                    Place(id="pasta", name="연남 파스타집", category="음식점 > 양식 > 이탈리안",
                          lat=37.5612, lng=126.9252, rating=4.5, rating_count=200,
                          open_time=time(11), close_time=time(22)),
                    *base,
                ]
            return base

    result = await generate_course("일요일 저녁 6시 연남동에서 파스타 먹고 와인바 가자", Ms())
    kinds = [classify(it.place) for it in result.timeline]
    assert kinds[0] == "meal" and kinds[-1] == "bar"
    assert result.timeline[0].place.id == "pasta"


def test_동네_중심을_안다():
    assert known_center("삼청동")[:2] == pytest.approx((37.5857, 126.9818), abs=1e-3)
    assert known_center("성수동") is not None
    assert known_center("어딘가모를동네") is None


def test_동네에서_먼_후보는_뺀다():
    near = [Place(id=f"n{i}", name="가", lat=37.5857, lng=126.9818 + i * 0.0001) for i in range(12)]
    far = Place(id="far", name="종로3가", lat=37.5705, lng=126.9920)  # 삼청동에서 약 1.9km
    kept = keep_near([*near, far], "삼청동")
    assert "far" not in {p.id for p in kept}
    # 남는 게 너무 적으면 그대로(후보가 없는 동네에서 빈 코스를 만들지 않는다)
    assert len(keep_near([near[0], far], "삼청동")) == 2


async def test_시간이_빠듯하면_완화를_건너뛴다(monkeypatch):
    from app.pipeline import agent, timing

    monkeypatch.setattr(agent, "RELAX_BUDGET_SEC", -1.0)
    calls = {"n": 0}
    real = agent._attempt

    async def counting(*a, **kw):
        calls["n"] += 1
        return (await real(*a, **kw))[:1]  # 늘 부족하게

    monkeypatch.setattr(agent, "_attempt", counting)
    timing.begin()
    result = await generate_course("성수동 저녁 데이트", MockMapService())
    assert calls["n"] == 1  # 완화 재시도(2번 더) 없이 끝냈다
    assert result.timeline
    assert any(name == "skip_relax_at_ms" for name, _ in timing.snapshot())


@pytest.mark.parametrize(
    "name,category,address",
    [
        ("망원한강공원 농구장2", "스포츠,레저 > 농구장", "서울 마포구 마포나루길 467"),
        ("[한성백제박물관] 주말가족교육", "행사", "한성백제박물관 교육실"),
        ("2026 문학 속 영화 투어", "행사", "서울시 전역"),
    ],
)
def test_데이트_할거리가_아닌_곳은_뺀다(name, category, address):
    from app.pipeline.planner import is_unfit_for_date

    assert is_unfit_for_date(Place(id="x", name=name, category=category, address=address, lat=37.5, lng=127.0))


def test_한강공원_자체는_할거리():
    from app.pipeline.planner import is_unfit_for_date

    assert not is_unfit_for_date(
        Place(id="x", name="망원한강공원", category="여행 > 공원", address="서울 마포구 마포나루길 467", lat=37.55, lng=126.9)
    )


def test_공원_편의시설은_할거리가_아니다():
    from app.pipeline.planner import is_unfit_for_date

    assert is_unfit_for_date(
        Place(id="x", name="한강공원망원7 개방화장실", category="화장실", address="서울 마포구 망원동", lat=37.55, lng=126.9)
    )


def test_한옥_초점은_문화_행사를_고르지_않는다():
    words = intent.match_words("한옥마을")
    assert not intent.satisfies(Place(id="e", name="2026 문화가 흐르는 서울광장", category="행사", lat=37.56, lng=126.97), words)
    assert intent.satisfies(Place(id="h", name="북촌한옥마을", category="관광명소", lat=37.58, lng=126.98), words)


def test_시간_모르는_전시_카페는_밤늦게_넣지_않는다():
    from app.pipeline.validation import is_open_during

    show = Place(id="s", name="특별 전시", category="전시/미술", lat=37.5, lng=127.0)
    cafe = Place(id="c", name="카페07", category="카페", lat=37.5, lng=127.0)
    bar = Place(id="b", name="와인주택", category="와인바", lat=37.5, lng=127.0)
    assert not is_open_during(show, time(22, 43), time(23, 43))
    assert not is_open_during(cafe, time(0, 22), time(1, 22))
    assert is_open_during(cafe, time(15, 0), time(16, 0))
    assert is_open_during(bar, time(22, 43), time(23, 43))  # 술집은 늦게까지 여는 곳이 많다


def test_밤_9시_이후는_술집_두_곳():
    assert desired_slots(parse_constraints("금요일 밤 9시 홍대에서 심야 데이트")) == ["bar", "bar"]
    # 개수를 말했거나 순서를 말했으면 그걸 따른다
    assert _slots("금요일 밤 9시 홍대 파스타 먹고 와인바") == ["meal", "cafe", "bar"]
