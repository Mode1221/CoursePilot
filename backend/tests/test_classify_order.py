"""카테고리 이름 분류는 구체적인 슬롯을 먼저 본다."""
import pytest

from app.pipeline.planner import classify
from app.schemas import Place


def _place(category: str) -> Place:
    return Place(id="p", name="가게", category=category, lat=37.5, lng=127.0)


@pytest.mark.parametrize(
    "category,slot",
    [
        ("음식점 > 술집 > 와인바", "bar"),
        ("음식점 > 술집 > 이자카야", "bar"),
        ("음식점 > 카페 > 브런치", "cafe"),
        ("음식점 > 카페 > 디저트", "cafe"),
        ("음식점 > 한식 > 국밥", "meal"),
        ("음식점 > 일식 > 초밥", "meal"),
        ("문화,예술 > 공연장", "activity"),
        ("여행 > 관광,명소 > 공원", "activity"),
    ],
)
def test_이름으로도_슬롯을_정확히_가른다(category, slot):
    assert classify(_place(category)) == slot


def test_카테고리_코드가_있으면_코드를_우선한다():
    place = _place("문화,예술 > 카페")
    place.category_code = "CE7"
    assert classify(place) == "cafe"


def test_알_수_없는_카테고리는_활동으로_둔다():
    assert classify(_place("기타 > 알 수 없음")) == "activity"
