import pytest

from app.reviews.rag import fetch_filtered


@pytest.mark.asyncio
async def test_mock_reviews_survive_sponsorship_filter():
    kept = await fetch_filtered("성수 카페", limit=10)
    # 협찬 표기 2건은 걸러지고, 나머지는 남아야 태그가 다양해진다
    assert len(kept) >= 4
    assert all("원고료" not in c and "제공받아" not in c for c in kept)


@pytest.mark.asyncio
async def test_mock_reviews_cover_multiple_aspects():
    from app.reviews.aspects import extract_aspects

    kept = await fetch_filtered("성수 카페", limit=10)
    pros, cons = extract_aspects(kept)
    assert len(pros) + len(cons) >= 3
