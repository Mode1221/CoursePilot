import pytest

from app.models import EMBED_DIM
from app.reviews.embedding import embed
from app.reviews.rag import ingest_place_reviews
from app.reviews.sponsored import is_sponsored, sponsored_score


def test_sponsored_filter():
    assert is_sponsored("업체로부터 제공받아 작성한 후기입니다")
    assert is_sponsored("소정의 원고료를 받아 작성")
    assert is_sponsored("체험단 방문")
    assert not is_sponsored("커피 맛있고 조용해요 재방문 의사 있음")


def test_sponsored_score_first_chunk_weighted():
    head = "협찬받은 후기입니다. " + "맛있어요 " * 30
    tail = "맛있어요 " * 30 + "협찬받았습니다"
    # 첫문단 표기가 본문 표기보다 강한 신호
    assert sponsored_score(head) > sponsored_score(tail)
    assert sponsored_score(head) >= 0.5


def test_sponsored_score_structure_and_account():
    clean = "조용하고 커피 맛있어요 재방문"
    assert sponsored_score(clean) == 0.0
    promo = clean + " 예약문의 카톡 쿠폰 할인코드"
    assert sponsored_score(promo) > 0
    # 계정 반복 신호 주입 시 가산
    assert sponsored_score(clean, account_repeat=True) > sponsored_score(clean)


@pytest.mark.asyncio
async def test_embed_dim():
    v = await embed("테스트 리뷰")
    assert len(v) == EMBED_DIM


@pytest.mark.asyncio
async def test_ingest_filters_sponsored_without_db():
    # Mock 소스 4건 중 협찬 2건 제외 → 2건 통과
    count = await ingest_place_reviews("p1", "테스트카페", db_ready=False)
    assert count == 2
