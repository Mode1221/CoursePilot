

def test_outlet_aspect():
    from app.reviews.aspects import extract_aspects

    pros, cons = extract_aspects(["콘센트 많아서 카공하기 좋아요"])
    assert "콘센트" in pros
    pros2, cons2 = extract_aspects(["콘센트 없어서 아쉬웠어요"])
    assert "콘센트" in cons2


def test_reservation_and_portion_aspects():
    from app.reviews.aspects import extract_aspects

    pros, cons = extract_aspects(["예약 필수인 곳이에요", "양 푸짐합니다"])
    assert "예약" in cons
    assert "양" in pros


def test_리뷰가_많으면_한두번_언급은_묻힌다():
    from app.reviews.aspects import extract_aspects

    reviews = ["주차 불가라 아쉬워요."] + ["평범했어요."] * 19
    pros, cons = extract_aspects(reviews)
    assert "주차" not in cons


def test_리뷰가_적으면_한_번_언급도_잡는다():
    from app.reviews.aspects import extract_aspects

    pros, cons = extract_aspects(["주차 불가라 아쉬워요."])
    assert "주차" in cons


def test_리뷰_아홉건에서도_태그가_남는다():
    """축마다 한 번씩 언급되는 흔한 묶음에서 요약이 비지 않아야 한다."""
    from app.reviews.aspects import extract_aspects

    reviews = [
        "웨이팅 30분 했는데 맛은 있어요",
        "주차가 정말 불편해요",
        "분위기 좋고 조용해서 대화하기 좋았어요",
        "직원분이 친절하시고",
        "가격 대비 양이 적어요",
        "콘센트 자리가 많아 노트북 하기 좋아요",
        "맛있었습니다",
        "화장실이 지저분했어요",
        "예약 안 하면 자리 없어요",
    ]
    pros, cons = extract_aspects(reviews)
    assert pros and cons
    assert "분위기" in pros
    assert "웨이팅" in cons


def test_리뷰가_많으면_기준이_엄격해진다():
    from app.reviews.aspects import _threshold

    assert _threshold(5) == 1
    assert _threshold(9) == 1
    assert _threshold(10) == 2
    assert _threshold(20) == 4
