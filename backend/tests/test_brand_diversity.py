"""같은 체인이 반복되지 않도록 후보를 고른다."""
from app.pipeline.planner import _pick_by_template, brand_key
from app.schemas import Place


def _place(pid: str, name: str, category: str) -> Place:
    return Place(id=pid, name=name, category=category, lat=37.5, lng=127.0)


def test_브랜드_키는_이름_첫_낱말():
    assert brand_key(_place("a", "스타벅스 성수점", "cafe")) == "스타벅스"


def test_같은_체인_대신_다른_브랜드를_고른다():
    ranked = [
        _place("s1", "스타벅스 성수점", "cafe"),
        _place("s2", "스타벅스 서울숲점", "cafe"),
        _place("c1", "어니언 성수", "cafe"),
    ]
    picked = _pick_by_template(ranked, ["cafe", "cafe"])
    assert [p.id for p in picked] == ["s1", "c1"]


def test_대안이_없으면_같은_체인도_쓴다():
    ranked = [
        _place("s1", "스타벅스 성수점", "cafe"),
        _place("s2", "스타벅스 서울숲점", "cafe"),
    ]
    picked = _pick_by_template(ranked, ["cafe", "cafe"])
    assert [p.id for p in picked] == ["s1", "s2"]
