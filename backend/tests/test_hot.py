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


def test_문화행사는_데이트에_맞는_것만():
    from app.adapters.seoul_openapi import is_date_worthy, parse_cultural_events

    assert is_date_worthy("전시/미술", "현대공예 기증특별전", "서울공예박물관")
    assert is_date_worthy("콘서트", "재즈 나이트", "노들섬")
    assert not is_date_worthy("교육/체험", "우리나비 북토크", "서울아트책보고")
    assert not is_date_worthy("교육/체험", "책 읽어주는 사서", "구립증산도서관")
    assert not is_date_worthy("국악", "어린이 국악 교실", "구민회관")
    body = {"culturalEventInfo": {"row": [
        {"CODENAME": "전시/미술", "TITLE": "공예전", "PLACE": "서울공예박물관", "STRTDATE": "2026-09-01", "END_DATE": "2027-03-07",
         "LAT": "37.576", "LOT": "126.985"},
        {"CODENAME": "교육/체험", "TITLE": "특별강연", "PLACE": "홍익대학교 인문사회관", "STRTDATE": "2026-09-22", "END_DATE": "2026-09-23",
         "LAT": "37.551", "LOT": "126.924"},
    ]}}
    names = [e["name"] for e in parse_cultural_events(body, date(2026, 9, 22))]
    assert names == ["공예전"]


async def test_도시데이터_장소명_후보를_차례로_시도한다(monkeypatch):
    from app.adapters import seoul_openapi as so
    from app.config import settings

    monkeypatch.setattr(settings, "seoul_openapi_key", "k")
    so._RESOLVED.clear()
    tried = []

    class _Resp:
        def __init__(self, ok):
            self.ok = ok

        def raise_for_status(self):
            if not self.ok:
                raise RuntimeError("404")

        def json(self):
            return {"CITYDATA": {"LIVE_PPLTN_STTS": [{"AREA_CONGEST_LVL": "보통"}]}}

    class _Client:
        async def get(self, url):
            tried.append(url.rsplit("/", 1)[-1])
            return _Resp(url.endswith("종로·청계 관광특구"))

    st = await so.area_status(_Client(), "을지로")
    assert st.area == "종로·청계 관광특구" and tried[:2] == ["명동 관광특구", "종로·청계 관광특구"]
    tried.clear()
    await so.area_status(_Client(), "을지로")
    assert tried == ["종로·청계 관광특구"]  # 한 번 맞힌 이름은 기억한다


def test_데이터랩_API_HUB_주소는_공식_경로(monkeypatch):
    from app.adapters import naver_datalab
    from app.config import settings

    monkeypatch.setattr(settings, "naver_apihub_key_id", "id")
    monkeypatch.setattr(settings, "naver_apihub_key", "key")
    url, headers = naver_datalab.endpoint()
    assert url == "https://naverapihub.apigw.ntruss.com/search-trend/v1/search"
    assert headers["X-NCP-APIGW-API-KEY-ID"] == "id"


def test_데이터랩은_끝난_주만_요청한다():
    from app.adapters.naver_datalab import WEEKS, full_weeks

    start, end = full_weeks(date(2026, 9, 22))  # 화요일
    assert end == date(2026, 9, 20) and end.weekday() == 6  # 지난 일요일
    assert start.weekday() == 0 and (end - start).days + 1 == WEEKS * 7
    s2, e2 = full_weeks(date(2026, 9, 20))  # 일요일 당일이면 그 전 주 일요일까지(오늘은 아직 안 끝남)
    assert e2 == date(2026, 9, 13)


def test_이번_주가_덜_찬_값이_섞이면_성장률이_깎였다():
    # 실측 모양: 꾸준한 값 뒤 마지막(덜 찬) 주가 1/5 로 떨어짐 → 제자리 가게가 '하락 중'으로 보였다
    partial = [60.0] * 12 + [64.0, 61.7, 60.5, 12.9]
    full = [60.0] * 12 + [64.0, 61.7, 60.5, 62.0]
    assert trend_from_series(partial).growth < 0.9  # 덜 찬 주를 넣으면 하락으로 오판
    assert trend_from_series(full).growth > 1.0  # 끝난 주만이면 제자리~소폭 상승
    # 진짜로 뜨는 가게도 덜 찬 주 하나에 성장률 1.75 → 1.36, 핫플 점수는 절반 가까이로 깎였다
    rising_partial = trend_from_series([20.0] * 12 + [30.0, 34.0, 38.0, 8.0])
    rising_full = trend_from_series([20.0] * 12 + [30.0, 34.0, 38.0, 41.0])
    assert rising_partial.growth < rising_full.growth * 0.8
    s_partial = combine(rising_partial, None, None, None, TODAY).score
    s_full = combine(rising_full, None, None, None, TODAY).score
    assert s_partial < s_full * 0.75


def test_도시데이터_행사는_제목으로_거르고_기간에서_종료일을_읽는다():
    from app.adapters.seoul_openapi import is_date_worthy_text, period_end

    assert not is_date_worthy_text("2026년 집옥재(팔우정 포함) 작은 도서관 개방", "경복궁 집옥재")
    assert not is_date_worthy_text("2026 길 위의 인문학·지혜학교", "대한민국전통예술전승원")
    assert is_date_worthy_text("2026년 경복궁 [경회루·향원정] 특별관람", "경복궁 경회루")
    assert period_end("2026-09-01~2026-10-01") == "2026-10-01"
    assert period_end("2026.09.10 ~ 2026.11.3") == "2026-11-03"
    assert period_end("상시") is None


async def test_핫플_배치는_상권마다_진행을_알리고_중간_결과를_넘긴다(monkeypatch):
    from app.batch import hot_refresh
    from app.batch.districts import DISTRICTS

    async def _trends(client, names, today=None):
        return {}

    async def _blog(client, q, display=100):
        return []

    monkeypatch.setattr(hot_refresh.naver_datalab, "weekly_trends", _trends)
    monkeypatch.setattr(hot_refresh, "_blog_items", _blog)
    d = DISTRICTS[0]
    places = [Place(id=f"p{i}", name=f"가게{i}", lat=d.lat, lng=d.lng) for i in range(3)]
    seen = []
    out = await hot_refresh.refresh_hotness(places, TODAY, on_district=lambda n, i, t, b: seen.append((n, len(b))))
    assert len(out) == 3 and seen and seen[0] == (d.name, 3) and len(seen) == len(DISTRICTS)
    assert all(p.hot_checked_at for p in out)
