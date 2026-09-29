"""키 없이 전체 흐름을 돌려 보기 위한 시드 장소 생성.

VM 에 올린 뒤 카카오 키가 오기 전에도 코스 생성·편집·공유·실시간이 실제로
도는지 봐야 한다. 그러려면 "그럴듯한" 장소가 상권마다 충분히 있어야 한다.
분포(카테고리 비율·영업시간·가격대·평점)를 실제와 비슷하게 맞추는 이유는,
플래너가 슬롯을 채우고 예산·영업시간 제약을 실제처럼 밟게 하기 위해서다.

만든 장소에는 is_mock 을 세워 실데이터가 들어오면 한 번에 지울 수 있게 한다.
"""
from __future__ import annotations

import random
from datetime import date, time, timedelta

from app.batch.districts import DISTRICTS, District
from app.schemas import Place

# 상권 하나에 만들 장소 수(실제 상권의 음식점·카페 밀도와 비슷한 범위)
MIN_PER_DISTRICT = 100
MAX_PER_DISTRICT = 200

# 슬롯 비중. 실제 상권도 밥집이 가장 많고 술집·볼거리가 그다음이다.
SLOT_WEIGHTS: dict[str, float] = {"meal": 0.45, "cafe": 0.25, "bar": 0.15, "activity": 0.15}

# 슬롯 → (카카오 그룹코드, 세부 카테고리 후보)
SLOT_CATEGORY: dict[str, tuple[str, tuple[str, ...]]] = {
    "meal": ("FD6", (
        "음식점 > 한식 > 육류,고기", "음식점 > 한식 > 국수", "음식점 > 일식 > 스시",
        "음식점 > 중식", "음식점 > 양식 > 파스타", "음식점 > 분식",
    )),
    "cafe": ("CE7", (
        "음식점 > 카페 > 커피전문점", "음식점 > 카페 > 디저트", "음식점 > 카페 > 베이커리",
    )),
    "bar": ("FD6", (
        "음식점 > 술집 > 요리주점", "음식점 > 술집 > 와인바", "음식점 > 술집 > 호프",
        "음식점 > 술집 > 이자카야",
    )),
    "activity": ("CT1", (
        "문화,예술 > 전시관", "문화,예술 > 공연장", "여행 > 관광,명소 > 공원",
        "스포츠,레저 > 볼링장", "문화,예술 > 문화시설",
    )),
}

# 1인 예상 비용 범위(원). 예산 제약이 실제처럼 걸리도록 슬롯별로 다르게 잡는다.
PRICE_RANGE: dict[str, tuple[int, int]] = {
    "meal": (9_000, 45_000),
    "cafe": (4_500, 13_000),
    "bar": (18_000, 60_000),
    "activity": (0, 25_000),
}

# 영업시간 패턴: (개점, 폐점, 브레이크 확률)
HOURS: dict[str, tuple[time, time, float]] = {
    "meal": (time(11, 0), time(22, 0), 0.35),   # 점심·저녁 사이 브레이크가 흔하다
    "cafe": (time(9, 0), time(22, 0), 0.05),
    "bar": (time(18, 0), time(2, 0), 0.0),      # 자정을 넘겨 닫는다
    "activity": (time(10, 0), time(18, 0), 0.1),
}

_NAME_PARTS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "meal": (("옛맛", "우리", "골목", "청춘", "소문난", "한상", "미가", "별미", "정담", "다올"),
             ("식당", "밥상", "정육식당", "국수집", "스시", "면옥", "반점", "키친")),
    "cafe": (("서린", "온담", "그린", "하루", "무드", "브릭", "여백", "모닝", "포레", "리버"),
             ("커피", "로스터스", "카페", "베이커리", "디저트")),
    "bar": (("달빛", "낮술", "골목", "취향", "야밤", "노포", "한잔", "비어", "청담", "온더")),
    # 볼거리는 이름과 종류가 어긋나면 어색하다("예술전시관"인데 공원) → 종류에서 이름을 만든다
    "activity": (("도시", "빛", "한강", "골목", "시민", "문화", "예술", "청년", "소소", "라온"),
                 ()),
}
_BAR_SUFFIX = ("포차", "주점", "와인바", "이자카야", "호프", "바")


# 볼거리 세부 카테고리 → 이름 끝에 붙일 말
_ACTIVITY_SUFFIX: dict[str, tuple[str, ...]] = {
    "전시관": ("전시관", "갤러리"),
    "공연장": ("아트홀", "공연장"),
    "공원": ("공원", "녹지원"),
    "볼링장": ("볼링장", "볼링클럽"),
    "문화시설": ("문화센터", "문화의집"),
}


def _name(rng: random.Random, slot: str, district: str, category: str = "") -> str:
    if slot == "activity":
        kind = category.split(">")[-1].strip()
        heads, _ = _NAME_PARTS["activity"]
        tails = _ACTIVITY_SUFFIX.get(kind, ("문화센터",))
        return f"{rng.choice(heads)} {rng.choice(tails)}"
    if slot == "bar":
        head = rng.choice(_NAME_PARTS["bar"])
        return f"{head}{rng.choice(_BAR_SUFFIX)}"
    heads, tails = _NAME_PARTS[slot]
    name = f"{rng.choice(heads)}{rng.choice(tails)}"
    # 일부는 지점명을 붙인다(같은 이름이 여러 상권에 있는 실제 상황)
    return f"{name} {district}점" if rng.random() < 0.25 else name


def _point_in_circle(rng: random.Random, district: District) -> tuple[float, float]:
    """상권 원 안에 고르게 흩는다(중심에 몰리지 않도록 반지름은 제곱근으로)."""
    angle = rng.random() * 6.283185
    radius = district.radius_m * (rng.random() ** 0.5)
    dlat = radius * __import__("math").cos(angle) / 111_000
    dlng = radius * __import__("math").sin(angle) / (111_000 * 0.79)  # 위도 37.5 보정
    return district.lat + dlat, district.lng + dlng


def _hours(rng: random.Random, slot: str) -> dict:
    open_time, close_time, break_chance = HOURS[slot]
    # 가게마다 ±1시간쯤 다르다
    open_h = (open_time.hour + rng.choice([-1, 0, 0, 1])) % 24
    close_h = (close_time.hour + rng.choice([-1, 0, 0, 1])) % 24
    values: dict = {"open_time": time(open_h, 0), "close_time": time(close_h, 0)}
    if rng.random() < break_chance:
        values["break_start"] = time(15, 0)
        values["break_end"] = time(17, 0)
    return values


def _rating(rng: random.Random) -> dict:
    """평점은 대체로 높고(3.8~4.7), 표본 수는 편차가 크다."""
    if rng.random() < 0.15:
        return {}  # 평점이 아예 없는 곳도 있다
    count = int(rng.lognormvariate(4.6, 1.0))  # 중앙값 100 안팎, 꼬리가 길다
    return {"rating": round(rng.uniform(3.5, 4.9), 1), "rating_count": max(3, min(count, 5000))}


def seed_places(
    districts: tuple[District, ...] = DISTRICTS, *, seed: int = 20260910
) -> list[Place]:
    """상권별 시드 장소. 같은 seed 면 항상 같은 결과(재실행이 중복을 만들지 않는다)."""
    places: list[Place] = []
    slots = list(SLOT_WEIGHTS)
    weights = [SLOT_WEIGHTS[s] for s in slots]
    today = date.today()

    for district in districts:
        rng = random.Random(f"{seed}:{district.name}")
        count = rng.randint(MIN_PER_DISTRICT, MAX_PER_DISTRICT)
        for index in range(count):
            slot = rng.choices(slots, weights=weights, k=1)[0]
            group_code, categories = SLOT_CATEGORY[slot]
            category = rng.choice(categories)
            lat, lng = _point_in_circle(rng, district)
            low, high = PRICE_RANGE[slot]
            places.append(
                Place(
                    # 상권·순번으로 정해지므로 다시 돌려도 같은 id → upsert 가 덮어쓴다
                    id=f"mock-{district.name}-{index:03d}",
                    name=_name(rng, slot, district.name, category),
                    category=category,
                    category_code=group_code,
                    address=f"서울 {district.sigungu} {district.name}로 {rng.randint(1, 99)}",
                    lat=round(lat, 6),
                    lng=round(lng, 6),
                    price=round(rng.uniform(low, high) / 500) * 500 if high else 0,
                    price_estimated=False,
                    opened_on=today - timedelta(days=rng.randint(120, 365 * 18)),
                    blog_mentions=int(rng.lognormvariate(5.0, 1.2)),
                    is_mock=True,
                    **_hours(rng, slot),
                    **_rating(rng),
                )
            )
    return places
