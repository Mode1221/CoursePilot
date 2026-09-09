"""1인 예상 비용 추정.

카카오·네이버 검색 결과에는 가격이 없다. 그래서 예산 조건("1인 3만원")이
실데이터에서는 아무것도 거르지 못했다. 정확한 가격을 알 수 없으니 카테고리
기준의 보수적인 1인 추정치를 넣고, 추정이라는 사실을 함께 표시한다.

추정치는 감이 아니라 조정 가능한 값으로 여기 모아 둔다(계수와 같은 취급).
"""
from __future__ import annotations

from app.schemas import Place

# 카테고리 세부 표기 → 1인 추정 비용(원). 더 구체적인 표기가 먼저 온다.
CATEGORY_PRICES: tuple[tuple[str, int], ...] = (
    ("오마카세", 90_000),
    ("스시", 40_000),
    ("횟집", 40_000),
    ("한정식", 35_000),
    ("이탈리", 30_000),
    ("스테이크", 45_000),
    ("고기", 25_000),
    ("구이", 25_000),
    ("뷔페", 30_000),
    ("이자카야", 25_000),
    ("와인", 30_000),
    ("칵테일", 20_000),
    ("위스키", 30_000),
    ("호프", 18_000),
    ("포차", 18_000),
    ("술집", 20_000),
    ("치킨", 20_000),
    ("피자", 18_000),
    ("일식", 20_000),
    ("중식", 15_000),
    ("양식", 25_000),
    ("한식", 15_000),
    ("분식", 8_000),
    ("국수", 10_000),
    ("베이커리", 8_000),
    ("디저트", 9_000),
    ("카페", 7_000),
    ("전시", 15_000),
    ("공연", 40_000),
    ("영화", 15_000),
    ("방탈출", 25_000),
    ("볼링", 15_000),
    ("노래", 10_000),
    ("박물관", 5_000),
    ("공원", 0),
    ("산책", 0),
)

# 슬롯별 기본값(세부 표기를 못 찾았을 때)
SLOT_PRICES = {"meal": 15_000, "cafe": 7_000, "bar": 20_000, "activity": 10_000}


def estimate_price(place: Place) -> int | None:
    """카테고리로 1인 비용을 추정한다. 판단할 근거가 없으면 None."""
    haystack = f"{place.category or ''} {place.name}"
    for keyword, price in CATEGORY_PRICES:
        if keyword in haystack:
            return price
    from app.pipeline.planner import classify

    return SLOT_PRICES.get(classify(place))


def fill_estimated_prices(places: list[Place]) -> list[Place]:
    """가격이 없는 장소만 추정치로 채우고 '추정'으로 표시한다."""
    for place in places:
        if place.price is not None:
            continue
        estimated = estimate_price(place)
        if estimated is None:
            continue
        place.price = estimated
        place.price_estimated = True
    return places
