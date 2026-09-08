import pytest

from app.reviews.source import MockReviewSource, RawReview, ReviewSource, SafeReviewSource


class _Boom(ReviewSource):
    async def fetch(self, place_name: str, limit: int = 10) -> list[RawReview]:
        raise RuntimeError("api down")


class _Fine(ReviewSource):
    async def fetch(self, place_name: str, limit: int = 10) -> list[RawReview]:
        return [RawReview("primary", "좋았어요", rating=5.0)]


@pytest.mark.asyncio
async def test_falls_back_when_primary_fails():
    src = SafeReviewSource(_Boom(), MockReviewSource())
    reviews = await src.fetch("성수 카페", limit=3)
    assert reviews  # Mock 결과로 이어진다


@pytest.mark.asyncio
async def test_uses_primary_when_healthy():
    src = SafeReviewSource(_Fine(), MockReviewSource())
    reviews = await src.fetch("성수 카페")
    assert reviews[0].source == "primary"
