"""핫플 신호·팝업·서울 도시데이터 — 순수 함수."""
from datetime import date, timedelta

from app.hot.popups import active_window, event_to_place, last_mention, looks_like_popup
from app.hot.signals import BlogSignal, TrendSignal, blog_from_items, combine, trend_from_series
from app.schemas import Place, PlanConstraints

TODAY = date(2026, 9, 22)


def _post(days_ago: int, sponsored: bool = False) -> dict:
    d = TODAY - timedelta(days=days_ago)
    return {"postdate": d.strftime("%Y%m%d"), "title": "성수 카페", "description": "체험단으로 제공받아 작성" if sponsored else "내돈내산 후기"}


def test_검색_트렌드_상승과_스파이크를_구분한다():
    steady = [10] * 8 + [14, 16, 18, 20]
    t = trend_from_series(steady)
    assert t.growth and t.growth > 1.3 and t.steady_rise and not t.spike
    spike = [10] * 8 + [10, 80, 12, 8]
    assert trend_from_series(spike).spike
    assert trend_from_series([1, 2]).growth is None  # 표본 부족


def test_블로그는_협찬을_빼고_세고_협찬_비율을_남긴다():
    items = [_post(3), _post(5), _post(10, sponsored=True), _post(40), _post(90)]
    b = blog_from_items(items, TODAY)
    assert b.recent == 2 and b.previous == 1 and b.sampled == 4
    assert b.sponsored_ratio == 0.25


def test_블로그만으로는_핫플이_될_수_없다():
    blog = BlogSignal(recent=40, previous=2, sponsored_ratio=0.1, sampled=42)
    h = combine(TrendSignal(growth=1.0), blog, None, TODAY - timedelta(days=30), TODAY)
    assert h.score == 0 and h.reasons == []


def test_검색량이_오르면_핫플이고_블로그_신상은_가산():
    h = combine(TrendSignal(growth=1.8, steady_rise=True), BlogSignal(recent=10, previous=3, sampled=13), None,
                TODAY - timedelta(days=100), TODAY)
    assert h.score > 0.5 and "최근 검색량 증가" in h.reasons and "1년 안에 생긴 곳" in h.reasons


def test_최근_글이_협찬_위주면_감점():
    base = combine(TrendSignal(growth=1.8), BlogSignal(recent=5, previous=2, sponsored_ratio=0.1, sampled=10), None, None, TODAY)
    ad = combine(TrendSignal(growth=1.8), BlogSignal(recent=5, previous=2, sponsored_ratio=0.7, sampled=10), None, None, TODAY)
    assert ad.score < base.score


def test_리뷰_증가도_주_신호():
    h = combine(None, None, 1.3, None, TODAY)
    assert h.score > 0 and "리뷰가 꾸준히 늘고 있음" in h.reasons


def test_팝업은_최근_언급이_있을_때만_진행_중():
    assert active_window(TODAY - timedelta(days=5), TODAY) == TODAY + timedelta(days=9)
    assert active_window(TODAY - timedelta(days=40), TODAY) is None
    assert last_mention([_post(3), _post(10)]) == TODAY - timedelta(days=3)
    assert looks_like_popup(Place(id="1", name="젠틀몬스터 팝업스토어", lat=0, lng=0))


def test_행사를_장소로_바꾸고_무료면_0원():
    p = event_to_place({"name": "서울 사진전", "kind": "전시/미술", "place": "DDP", "lat": 37.566, "lng": 127.009,
                        "end": "2026-10-05", "is_free": True}, "")
    assert p.is_popup and p.price == 0 and p.active_until == date(2026, 10, 5) and p.category_code == "CT1"


def test_끝난_팝업은_후보에서_빠지고_팝업은_할거리_칸():
    from app.pipeline.planner import classify

    live = Place(id="a", name="A 팝업스토어", lat=0, lng=0, is_popup=True, active_until=TODAY + timedelta(days=3))
    assert classify(live) == "activity"


def test_핫플_요청이면_핫플_가점이_커지고_업력_가점이_빠진다():
    from app.pipeline.planner import is_hot_request, score_place

    hot = Place(id="h", name="신상 카페", category="카페", lat=0, lng=0, hot_score=0.8)
    plain = PlanConstraints(keywords=["카페"])
    trendy = PlanConstraints(keywords=["요즘 핫플"])
    assert is_hot_request(trendy) and not is_hot_request(plain)
    assert score_place(hot, trendy, None) > score_place(hot, plain, None)


def test_서울_도시데이터_응답을_읽는다():
    from app.adapters.seoul_openapi import parse_citydata

    body = {"CITYDATA": {"LIVE_PPLTN_STTS": [{"AREA_CONGEST_LVL": "붐빔", "AREA_CONGEST_MSG": "사람이 많아요",
            "FCST_PPLTN": [{"FCST_TIME": "2026-09-22 17:00", "FCST_CONGEST_LVL": "보통"},
                           {"FCST_TIME": "2026-09-22 20:00", "FCST_CONGEST_LVL": "여유"}]}],
            "EVENT_STTS": [{"EVENT_NM": "성수 전시", "EVENT_PLACE": "성수", "EVENT_PERIOD": "2026-09-01~2026-10-01",
                            "EVENT_X": "127.05", "EVENT_Y": "37.54"}]}}
    st = parse_citydata(body, "성수카페거리")
    assert st.level == "붐빔" and st.calmer_hour == "20시" and st.events[0]["lat"] == 37.54


def test_키가_없으면_혼잡도는_null():
    from fastapi.testclient import TestClient

    from app.main import api

    assert TestClient(api).get("/areas/status", params={"region": "성수"}).json() is None
