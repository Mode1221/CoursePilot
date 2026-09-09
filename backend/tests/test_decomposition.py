

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


def test_시작만_말하고_종료를_까지로_붙이는_표현():
    from datetime import time

    from app.pipeline.decomposition import parse_constraints

    c = parse_constraints("저녁 6시에 만나서 11시까지 성수동")
    assert c.start_time == time(18, 0)
    assert c.end_time == time(23, 0)
    assert c.duration_min == 300
    # 자정을 넘겨도 이어진다
    late = parse_constraints("밤 10시에 만나서 1시까지")
    assert late.end_time == time(1, 0)
    assert late.duration_min == 180


def test_다음달_날짜를_인식한다():
    from datetime import date

    from app.pipeline.decomposition import _parse_date

    assert _parse_date("다음달 5일 저녁", date(2026, 9, 9)) == date(2026, 10, 5)
    assert _parse_date("담달 20일", date(2026, 12, 1)) == date(2027, 1, 20)


def test_한글_수사_소요시간과_퇴근_표현():
    from datetime import time

    from app.pipeline.decomposition import parse_constraints

    c = parse_constraints("퇴근 후 성수동 두 시간")
    assert c.start_time == time(19, 0)
    assert c.duration_min == 120
    assert c.end_time == time(21, 0)

    assert parse_constraints("한 시간 안에 끝나는 코스").duration_min == 60
    assert parse_constraints("세 시간 반 정도").duration_min == 210
    # 방문 개수 표현("두 곳")과 섞이지 않는다
    assert parse_constraints("두 곳만 가고 싶어").duration_min is None


def test_지명_접미사_오탐을_거른다():
    from app.pipeline.decomposition import parse_constraints

    # "친구"의 '구', "아니면"의 '면'이 지명으로 잡히면 엉뚱한 검색어가 된다
    assert parse_constraints("친구랑 놀 데 추천해줘").region is None
    assert parse_constraints("강남 아니면 홍대").region == "홍대"
    assert parse_constraints("라면 먹고 카페").region is None
    # 진짜 지명은 그대로 인식
    assert parse_constraints("성수동 저녁").region == "성수동"
    assert parse_constraints("서초구 점심").region == "서초구"
    assert parse_constraints("대구 저녁").region == "대구"


def test_아이_어르신_동반_표현을_가족으로_본다():
    from app.pipeline.decomposition import parse_constraints

    for text in ("애들이랑 갈 만한 곳", "유모차 끌고 갈 데", "어르신이랑 점심", "임산부도 괜찮은 곳"):
        assert parse_constraints(text).companion == "가족", text
    # 다른 동행유형은 그대로
    assert parse_constraints("친구랑 술 한잔").companion == "친구"


def test_동반_조건_검색어를_인식한다():
    from app.pipeline.decomposition import parse_constraints

    assert "키즈존" in parse_constraints("키즈존 있는 카페").keywords
    assert "좌식" in parse_constraints("좌식 자리 있는 한식당").keywords
