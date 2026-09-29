"""리뷰 원문 없이 얻는 품질 신호: 평가 수 신뢰도·업력·인근 폐업률·등재·인지도."""
from datetime import date, timedelta

from app.adapters.localdata import LocalDataRegistry
from app.pipeline.planner import (
    LONGEVITY_CAP_YEARS,
    MIN_TRUSTED_RATINGS,
    awareness_signal,
    closure_signal,
    longevity_signal,
    score_place,
)
from app.schemas import Place, PlanConstraints

C = PlanConstraints()


def _place(**kw) -> Place:
    return Place(**{"id": "p", "name": "가게", "lat": 37.5, "lng": 127.0, **kw})


def test_표본이_적은_평점은_쓰지_않는다():
    few = _place(rating=5.0, rating_count=MIN_TRUSTED_RATINGS - 1)
    many = _place(rating=4.3, rating_count=800)
    assert score_place(many, C, None) > score_place(few, C, None)


def test_표본을_모르면_종전대로_평점을_쓴다():
    assert score_place(_place(rating=4.5), C, None) > score_place(_place(), C, None)


def test_업력이_길수록_가점되고_상한이_있다():
    today = date.today()
    assert longevity_signal(_place()) == 0.0
    young = longevity_signal(_place(opened_on=today - timedelta(days=400)))
    old = longevity_signal(_place(opened_on=today - timedelta(days=365 * 10)))
    capped = longevity_signal(
        _place(opened_on=today - timedelta(days=365 * (LONGEVITY_CAP_YEARS + 30)))
    )
    assert 0 < young < old <= capped == 1.0


def test_개업_직후는_가점이_없다():
    assert longevity_signal(_place(opened_on=date.today())) == 0.0


def test_오래된_가게가_더_높은_점수를_받는다():
    old = _place(opened_on=date.today() - timedelta(days=365 * 12))
    new = _place(opened_on=date.today() - timedelta(days=30))
    assert score_place(old, C, None) > score_place(new, C, None)


def test_인근_폐업률이_높으면_감점된다(monkeypatch):
    monkeypatch.setattr(
        "app.adapters.localdata.get_localdata_registry",
        lambda: _FakeRegistry(0.6),
    )
    risky = _place(address="서울 성동구 성수동")
    monkeypatch.setattr("app.pipeline.planner.closure_signal", lambda p: 0.6)
    assert score_place(risky, C, None) < 0


class _FakeRegistry(LocalDataRegistry):
    def __init__(self, rate):
        super().__init__()
        self._rate = rate

    def closure_rate(self, address):
        return self._rate


def test_폐업률을_모르면_중립이다(monkeypatch):
    monkeypatch.setattr(
        "app.adapters.localdata.get_localdata_registry", lambda: _FakeRegistry(None)
    )
    assert closure_signal(_place(address="어딘가")) is None
    assert score_place(_place(address="어딘가"), C, None) == 0.0


def test_폐업률_조회_실패는_중립이다(monkeypatch):
    def boom():
        raise RuntimeError("db down")

    monkeypatch.setattr("app.adapters.localdata.get_localdata_registry", boom)
    assert closure_signal(_place(address="어딘가")) is None


def test_관광_문화_등재는_가점된다():
    assert score_place(_place(tour_listed=True), C, None) > score_place(_place(), C, None)


def test_인지도는_건수_로그로_포화한다():
    assert awareness_signal(_place()) == 0.0
    small = awareness_signal(_place(blog_mentions=10))
    big = awareness_signal(_place(blog_mentions=2000))
    huge = awareness_signal(_place(blog_mentions=100_000))
    assert 0 < small < big <= huge == 1.0


def test_인지도가_높으면_점수가_높다():
    assert score_place(_place(blog_mentions=5000), C, None) > score_place(_place(), C, None)
