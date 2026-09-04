import pytest

from app.reviews.embedding import embed
from app.reviews.rag import ingest_place_reviews
from app.reviews.sponsored import is_sponsored
from app.models import EMBED_DIM


def test_sponsored_filter():
    assert is_sponsored("업체로부터 제공받아 작성한 후기입니다")
    assert is_sponsored("소정의 원고료를 받아 작성")
    assert is_sponsored("체험단 방문")
    assert not is_sponsored("커피 맛있고 조용해요 재방문 의사 있음")


@pytest.mark.asyncio
async def test_embed_dim():
    v = await embed("테스트 리뷰")
    assert len(v) == EMBED_DIM


@pytest.mark.asyncio
async def test_ingest_filters_sponsored_without_db():
    # Mock 소스 4건 중 협찬 2건 제외 → 2건 통과
    count = await ingest_place_reviews("p1", "테스트카페", db_ready=False)
    assert count == 2
