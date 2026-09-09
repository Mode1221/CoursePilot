"""온보딩 선호 프로필이 코스 조건에 반영되는지."""
from __future__ import annotations

from app.pipeline.agent import BUDGET_CHOICES, _apply_preferences
from app.pipeline.decomposition import parse_constraints
from app.schemas import TravelMode


def test_예산_문항이_1인_예산_상한이_된다():
    c = parse_constraints("성수동에서 저녁")
    _apply_preferences(c, {"budget": "2~4만원"})
    assert c.budget_max == 40000


def test_문장에_적힌_예산이_우선한다():
    c = parse_constraints("성수동 3만원 이하로 저녁")
    _apply_preferences(c, {"budget": "6만원 이상"})
    assert c.budget_max == 30000


def test_알_수_없는_예산_값은_무시한다():
    c = parse_constraints("성수동에서 저녁")
    _apply_preferences(c, {"budget": "아무거나"})
    assert c.budget_max is None


def test_식이_제한은_검색_키워드로_들어간다():
    c = parse_constraints("성수동에서 저녁")
    _apply_preferences(c, {"diet": ["비건", "노키즈"]})
    assert "비건" in c.keywords and "노키즈" in c.keywords


def test_지역_무드_이동수단도_보완한다():
    c = parse_constraints("저녁에 놀자")
    _apply_preferences(c, {"region": "연남동", "mood": "조용한", "transport": "차량"})
    assert c.region == "연남동"
    assert "조용한" in c.keywords
    assert c.travel_mode == TravelMode.CAR


def test_예산_문항은_네_개():
    assert len(BUDGET_CHOICES) == 4
