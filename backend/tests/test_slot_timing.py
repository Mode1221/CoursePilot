from datetime import time

from app.pipeline.planner import desired_slots
from app.schemas import PlanConstraints


def _slots(hour: int | None, minutes: int = 270, **kw) -> list[str]:
    start = time(hour, 0) if hour is not None else None
    return desired_slots(PlanConstraints(duration_min=minutes, start_time=start, **kw))


def test_점심_시간에_시작하면_식사부터():
    assert _slots(12)[0] == "meal"


def test_오전에_시작하면_식사를_점심시간으로_미룬다():
    slots = _slots(10)
    assert slots[0] != "meal"
    assert slots.index("meal") == 1  # 10시 + 2시간 = 12시


def test_늦은_오후에_시작하면_식사가_저녁시간으로():
    slots = _slots(15)
    assert slots[0] != "meal"
    assert slots.index("meal") == 1  # 15시 + 2시간 = 17시


def test_저녁에_시작하면_그대로_식사부터():
    assert _slots(19)[0] == "meal"


def test_시작_시각이_없으면_기존_순서_유지():
    assert _slots(None)[0] == "meal"


def test_회식_템플릿도_시간대를_따른다():
    slots = _slots(10, companion="회식")
    assert slots.index("meal") >= 1


def test_관람_체험은_카페보다_오래_머문다():
    from app.pipeline.validation import stay_minutes
    from app.schemas import Place

    def _p(cat: str) -> Place:
        return Place(id=cat, name=cat, category=cat, lat=37.5, lng=127.0)

    assert stay_minutes(_p("문화,예술>영화관")) == 150
    assert stay_minutes(_p("문화,예술>미술관")) == 90
    assert stay_minutes(_p("카페,디저트")) == 60
    assert stay_minutes(_p("음식점>한식")) == 90
