

def test_자정을_넘겨도_종료_시각을_잡는다():
    from datetime import time

    from app.pipeline.decomposition import parse_constraints

    c = parse_constraints("밤 11시부터 3시간 성수동")
    assert c.start_time == time(23, 0)
    assert c.end_time == time(2, 0)
    assert c.duration_min == 180


def test_마커_없는_이른_시각은_저녁으로_본다():
    from datetime import time

    from app.pipeline.decomposition import parse_constraints

    assert parse_constraints("금요일 7시 강남역 회식").start_time == time(19, 0)
    assert parse_constraints("6시에 만나자").start_time == time(18, 0)
    # 오전을 뜻하는 표현이 있으면 그대로 둔다
    assert parse_constraints("아침 7시 조깅").start_time == time(7, 0)
    assert parse_constraints("7시 브런치").start_time == time(7, 0)
    assert parse_constraints("오전 7시 모임").start_time == time(7, 0)
    # 8시 이상은 그대로(오전 가능성이 높다)
    assert parse_constraints("8시 시작").start_time == time(8, 0)


def test_지명이_아닌_단어를_지역으로_잡지_않는다():
    from app.pipeline.decomposition import parse_constraints

    assert parse_constraints("반려동물 동반 가능한 카페 망원").region == "망원"
    assert parse_constraints("성수동에서 만나자").region == "성수동"
    assert parse_constraints("종로구 맛집").region == "종로구"


def test_다른_말에_섞인_한_곳을_개수로_보지_않는다():
    from app.pipeline.decomposition import parse_constraints

    assert parse_constraints("성수동 카페 두 곳 조용한 곳으로").stop_count == 2
    assert parse_constraints("조용한 곳으로 추천해줘").stop_count is None
    assert parse_constraints("한 곳만 갈래").stop_count == 1


def test_동행_표현과_키워드를_더_넓게_인식한다():
    from app.pipeline.decomposition import parse_constraints

    assert parse_constraints("애인이랑 기념일 저녁").companion == "데이트"
    assert parse_constraints("소개팅 장소 추천").companion == "데이트"
    assert "커피" in parse_constraints("가볍게 커피만 마실 곳").keywords
    assert "보드게임" in parse_constraints("보드게임 카페 가고 싶어").keywords


def test_브런치는_기본_시작을_11시로_잡는다():
    from datetime import time

    from app.pipeline.decomposition import parse_constraints

    assert parse_constraints("연남동 브런치").start_time == time(11, 0)
    assert parse_constraints("조식 먹고 산책").start_time == time(11, 0)
    # 시각·시간대를 말했으면 그 값이 우선
    assert parse_constraints("아침 브런치").start_time == time(9, 0)
    assert parse_constraints("오후 2시 브런치").start_time == time(14, 0)


def test_접미사_없는_지명도_인식한다():
    from app.pipeline.decomposition import parse_constraints

    assert parse_constraints("광화문에서 점심 먹고 산책").region == "광화문"
    assert parse_constraints("대학로 연극 보고 저녁").region == "대학로"


def test_다른_키워드에_포함된_조각은_키워드로_보지_않는다():
    from app.pipeline.decomposition import parse_constraints

    # "산책"의 "책"이 별도 키워드로 잡히면 검색어가 오염된다
    assert parse_constraints("광화문에서 산책").keywords == ["산책"]
    assert "책" in parse_constraints("책 읽을 곳").keywords
