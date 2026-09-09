"""차수 표현("1차 고기 2차 술")."""
import pytest

from app.pipeline.decomposition import parse_constraints


@pytest.mark.parametrize(
    "text,expected",
    [
        ("1차 고기 2차 술", 2),
        ("강남에서 1차만", 1),
        ("1차 고기 2차 맥주 3차 노래방", 3),
        ("2차까지 갈까", 2),
        ("한 곳만 추천해줘", 1),
        ("세 군데 돌자", 3),
    ],
)
def test_마지막_차수가_장소_수가_된다(text, expected):
    assert parse_constraints(text).stop_count == expected


def test_차수에_붙은_음식_종류를_검색어로_쓴다():
    c = parse_constraints("금요일 퇴근하고 강남에서 6명 회식, 1차 고기 2차 맥주")
    assert "고기" in c.keywords and "맥주" in c.keywords
    assert c.party_size == 6 and c.companion == "회식"


def test_상한을_넘는_차수는_잘라낸다():
    assert parse_constraints("1차부터 9차까지 가자").stop_count == 6


def test_차수가_없으면_개수를_정하지_않는다():
    assert parse_constraints("성수동 데이트 코스").stop_count is None


def test_예술은_술로_읽지_않는다():
    c = parse_constraints("성수에서 예술 전시 보고 싶어")
    assert "술" not in c.keywords
