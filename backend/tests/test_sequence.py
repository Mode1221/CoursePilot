from app.pipeline.planner import seq_order
from app.schemas import Place
from app.sequence import SequenceStore, sequence_store


def _p(pid, category):
    return Place(id=pid, name=pid, category=category, rating=4.0, lat=37.5, lng=127.0)


def test_sequence_accumulates_and_scores():
    ss = SequenceStore()
    ss.bump_sequence(["meal", "cafe", "bar"])
    ss.bump_sequence(["meal", "cafe"])
    assert ss.transition("meal", "cafe") == 2.0
    assert ss.transition("cafe", "bar") == 1.0
    assert ss.transition("bar", "meal") == 0.0
    # meal→cafe→bar = 2 + 1
    assert ss.sequence_score(["meal", "cafe", "bar"]) == 3.0


def test_seq_order_follows_learned_transitions():
    sequence_store._mem.clear()
    # 학습: 식사 다음엔 술, 그다음 카페를 선호
    sequence_store.bump_sequence(["meal", "bar", "cafe"], weight=5)
    places = [_p("m", "restaurant"), _p("c", "cafe"), _p("b", "bar")]
    ordered = [p.id for p in seq_order(places)]
    assert ordered == ["m", "b", "c"]
    sequence_store._mem.clear()


def test_전이표를_통째로_읽는다():
    from app.sequence import SequenceStore

    store = SequenceStore()
    store.bump_sequence(["meal", "cafe", "bar"])
    table = store.all_transitions()
    assert table[("meal", "cafe")] == 1.0
    assert table[("cafe", "bar")] == 1.0
    assert store.sequence_score(["meal", "cafe", "bar"]) == 2.0
