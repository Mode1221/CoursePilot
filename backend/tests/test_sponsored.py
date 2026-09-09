

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


def test_본문_뒤쪽_표기도_걸러낸다():
    from app.reviews.rag import SPONSORED_THRESHOLD
    from app.reviews.sponsored import sponsored_score

    text = "여기 커피 맛있고 자리도 넓어요. " * 20 + "본 후기는 업체로부터 협찬을 받아 작성했습니다."
    assert sponsored_score(text) >= SPONSORED_THRESHOLD


def test_내돈내산_이면_표기_문구가_있어도_남긴다():
    from app.reviews.rag import SPONSORED_THRESHOLD
    from app.reviews.sponsored import sponsored_score

    text = "내돈내산 후기예요. " * 5 + "요즘 협찬 글이 많던데 저는 제 돈으로 갔습니다."
    assert sponsored_score(text) < SPONSORED_THRESHOLD
