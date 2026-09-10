"""리뷰 요약 폴백 경계."""


async def test_빈_리뷰만_있으면_참고했다고_말하지_않는다():
    """빈 문자열도 1건으로 세어 '리뷰 1건을 참고했어요'라고 답했다."""
    from app.reviews.rag import summarize_reviews

    assert await summarize_reviews([""]) == "참고할 리뷰가 없습니다."
    assert await summarize_reviews(["  ", "\n"]) == "참고할 리뷰가 없습니다."
