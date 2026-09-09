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


def test_광고_표기_변형을_잡는다():
    from app.reviews.sponsored import sponsored_score

    for text in (
        "본 포스팅은 광고를 포함하고 있습니다",
        "광고성 포스팅입니다",
        "업체와 제휴를 통해 방문했습니다",
        "브랜드와 협업으로 진행한 방문기",
    ):
        assert sponsored_score(text) >= 0.5, text
    # 일반 문장은 그대로 통과
    assert sponsored_score("친구랑 갔는데 광고판이 예뻤어요") < 0.5
