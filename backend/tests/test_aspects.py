

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
