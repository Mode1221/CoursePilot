"""공동채택 쌍 저장 상한(DB 미사용 모드)."""
from __future__ import annotations

from app.cooccurrence import EVICT_RATIO, MAX_PAIRS, CooccurrenceStore


def test_상한을_넘으면_약한_신호부터_버린다():
    store = CooccurrenceStore()
    # 약한 쌍을 상한까지 채운다
    for i in range(MAX_PAIRS):
        store._mem[frozenset((f"a{i}", f"b{i}"))] = 1.0
    # 강한 신호 하나를 만들어 두고
    strong = frozenset(("hot-1", "hot-2"))
    store._mem[strong] = 99.0

    store.bump_course(["x1", "x2"])  # 여기서 정리가 돌아간다

    assert len(store._mem) <= MAX_PAIRS
    assert store._mem[strong] == 99.0  # 강한 신호는 남는다
    assert store._mem[frozenset(("x1", "x2"))] == 1.0  # 새 신호도 들어간다


def test_상한_안에서는_정리하지_않는다():
    store = CooccurrenceStore()
    store.bump_course(["a", "b", "c"])
    assert len(store._mem) == 3
    assert 0 < EVICT_RATIO < 1
