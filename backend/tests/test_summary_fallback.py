import pytest

from app.reviews.rag import _tag_summary, summarize_reviews


def test_tag_summary_uses_tags_not_raw_text():
    reviews = ["웨이팅 없이 바로 입장했어요", "분위기 좋고 친절합니다"]
    summary = _tag_summary(reviews)
    assert "좋은 점" in summary
    # 원문이 그대로 노출되면 안 된다(약관: 원문 인용 회피)
    assert "바로 입장했어요" not in summary


def test_tag_summary_without_matches():
    assert "1건" in _tag_summary(["무난했습니다"])


@pytest.mark.asyncio
async def test_summarize_without_key_falls_back_to_tags():
    summary = await summarize_reviews(["주차 불가라 아쉬웠어요"])
    assert "주차" in summary
