import pytest

from app.adapters.map_service import MockMapService, SafeMapService
from app.metrics import metrics_store
from app.reviews.source import MockReviewSource, RawReview, ReviewSource, SafeReviewSource


class _BoomMap(MockMapService):
    async def search_places(self, *a, **k):
        raise RuntimeError("api down")


class _BoomReviews(ReviewSource):
    async def fetch(self, place_name: str, limit: int = 10) -> list[RawReview]:
        raise RuntimeError("api down")


def _externals() -> dict[str, dict]:
    return {e["name"]: e for e in metrics_store.snapshot()["externals"]}


@pytest.mark.asyncio
async def test_map_fallback_is_recorded():
    metrics_store.clear()
    await SafeMapService(_BoomMap(), MockMapService()).search_places("성수동", [], 3)
    assert _externals()["map.search_places"]["fallback"] == 1


@pytest.mark.asyncio
async def test_map_success_is_recorded():
    metrics_store.clear()
    await SafeMapService(MockMapService(), MockMapService()).search_places("성수동", [], 3)
    stat = _externals()["map.search_places"]
    assert stat["ok"] == 1
    assert stat["fallback_rate"] == 0.0


@pytest.mark.asyncio
async def test_review_fallback_is_recorded():
    metrics_store.clear()
    await SafeReviewSource(_BoomReviews(), MockReviewSource()).fetch("성수 카페")
    assert _externals()["reviews.fetch"]["fallback_rate"] == 1.0
