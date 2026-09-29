

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


def test_모임_코스에_중요한_축을_뽑는다():
    from app.reviews.aspects import extract_aspects

    pros, _ = extract_aspects(
        [
            "단체 가능해서 회식하기 좋아요",
            "한강뷰가 최고예요",
            "재방문 의사 있어요",
            "반려동물 동반 가능해서 좋았어요",
        ]
    )
    assert {"단체석", "뷰", "재방문", "반려동물"} <= set(pros)


def test_부정_표현도_조사와_함께_인식한다():
    from app.reviews.aspects import extract_aspects

    _, cons = extract_aspects(
        ["룸 없어서 아쉬웠어요", "애견 동반 불가라 아쉬움", "뷰가 별로", "다시는 안 갈래요"]
    )
    assert {"단체석", "반려동물", "뷰", "재방문"} <= set(cons)


def test_주차장_넓다는_말을_좌석으로_읽지_않는다():
    from app.reviews.aspects import extract_aspects

    pros, _ = extract_aspects(["주차장 넓어요", "주차 가능해요"])
    assert "주차" in pros and "좌석" not in pros


def test_자리_표현만_좌석으로_읽는다():
    from app.reviews.aspects import extract_aspects

    pros, _ = extract_aspects(["자리 넉넉해요", "테이블 많고 좋아요"])
    assert "좌석" in pros


def test_좁다는_말은_좌석_주의로_읽는다():
    from app.reviews.aspects import extract_aspects

    _, cons = extract_aspects(["매장이 좁아요", "자리가 없어요"])
    assert "좌석" in cons


def test_조사가_끼어도_축을_읽는다():
    from app.reviews.aspects import extract_aspects

    pros, cons = extract_aspects(["분위기는 좋은데 맛은 별로"])
    assert "분위기" in pros and "맛" in cons


def test_응대_위생_표현도_조사를_흡수한다():
    from app.reviews.aspects import extract_aspects

    _, cons = extract_aspects(["위생은 별로였어요", "응대가 별로"])
    assert "청결" in cons and "친절" in cons


def test_해시태그는_축으로_읽지_않는다():
    from app.reviews.aspects import extract_aspects

    pros, _ = extract_aspects(["#맛집 #성수동맛집 #카페추천 분위기 좋아요"])
    assert "분위기" in pros and "맛" not in pros


def test_본문의_같은_말은_그대로_읽는다():
    from app.reviews.aspects import extract_aspects

    pros, _ = extract_aspects(["맛있고 분위기 좋아요"])
    assert "맛" in pros and "분위기" in pros
