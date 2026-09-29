from app.reviews.aspects import extract_aspects


def test_긍정_부정_태그를_분리한다():
    pros, cons = extract_aspects(
        ["웨이팅이 너무 길었어요", "주차 불가라 아쉬움", "분위기 좋고 조용합니다", "가성비 최고"]
    )
    assert "웨이팅" in cons and "주차" in cons
    assert "분위기" in pros and "가성비" in pros


def test_같은_축은_더_많이_언급된_쪽만_남는다():
    pros, cons = extract_aspects(["웨이팅 길어요", "웨이팅 심함", "웨이팅 없어서 좋았어요"])
    assert "웨이팅" in cons
    assert "웨이팅" not in pros


def test_리뷰가_없으면_빈_태그():
    assert extract_aspects([]) == ([], [])


def test_태그는_최대_4개():
    pros, _ = extract_aspects(
        ["분위기 좋고 조용하고 가성비 좋고 친절하고 맛있고 깨끗하고 자리 넉넉"]
    )
    assert len(pros) <= 4
