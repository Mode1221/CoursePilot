"""합성 신호 리플레이 — 신호가 쌓이면 랭킹이 실제로 좋아지는가."""
from __future__ import annotations

import pytest

from app.pipeline.simulation import (
    build_catalog,
    rank_quality,
    replay,
    simulate_sessions,
    to_samples,
)


@pytest.fixture(autouse=True)
def _clear_stores():
    from app.cooccurrence import cooccurrence_store
    from app.popularity import popularity_store
    from app.sequence import sequence_store
    from app.timecontext import time_context_store

    stores = (popularity_store, time_context_store, cooccurrence_store, sequence_store)
    for st in stores:
        st._mem.clear()
    yield
    for st in stores:
        st._mem.clear()


def test_시뮬레이션은_시드로_결정론적이다():
    assert simulate_sessions(20) == simulate_sessions(20)
    assert simulate_sessions(20, seed=1) != simulate_sessions(20, seed=2)


def test_카탈로그_평점은_숨은_선호와_어긋난다():
    catalog = {p.id: p for p in build_catalog()}
    assert catalog["meal-0"].rating < catalog["meal-4"].rating


def test_신호가_쌓이면_랭킹이_좋아진다():
    train = simulate_sessions(200)
    test = to_samples(simulate_sessions(60, seed=99))

    before = rank_quality(test)
    replay(train)
    after = rank_quality(test)

    assert before.top1 < 0.2  # 평점만 보면 숨은 선호를 거의 못 맞힌다
    assert after.top1 > 0.4  # 인기·시간대 신호가 평점 편향을 이긴다
    assert after.mrr > before.mrr


def test_리플레이가_시퀀스_전이도_남긴다():
    from app.sequence import sequence_store

    replay(simulate_sessions(50))
    assert sequence_store.all_transitions()
