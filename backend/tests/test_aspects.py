

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
