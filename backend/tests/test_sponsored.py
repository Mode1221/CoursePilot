

def test_supporters_and_ambassador_detected():
    from app.reviews.sponsored import sponsored_score

    assert sponsored_score("서포터즈로 방문했습니다") >= 0.5
    assert sponsored_score("앰배서더 활동으로 다녀왔어요") >= 0.5


def test_self_paid_lowers_score():
    from app.reviews.sponsored import sponsored_score

    plain = sponsored_score("쿠폰 받아서 갔어요 예약 문의 주세요")
    self_paid = sponsored_score("내돈내산 후기입니다. 쿠폰 받아서 갔어요 예약 문의 주세요")
    assert self_paid < plain


def test_score_never_negative():
    from app.reviews.sponsored import sponsored_score

    assert sponsored_score("내돈내산 조용하고 좋았어요") == 0.0
