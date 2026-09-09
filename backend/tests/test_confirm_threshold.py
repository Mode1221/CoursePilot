"""완화 확인 프롬프트 기준 — 2곳이면 되묻지 않는다."""
from __future__ import annotations

from app.adapters.map_service import get_map_service
from app.pipeline.agent import _min_usable, generate_course
from app.pipeline.decomposition import parse_constraints


def test_개수를_말하지_않으면_두곳이면_충분():
    c = parse_constraints("성수동에서 저녁 데이트")
    assert _min_usable(c) == 2


def test_개수를_말했으면_그_수가_기준():
    c = parse_constraints("성수동 세 곳 가고 싶어")
    assert c.stop_count == 3
    assert _min_usable(c) == 3


async def test_두곳짜리_코스는_확인을_요구하지_않는다():
    result = await generate_course("성수동에서 술 빼고 저녁 데이트", get_map_service())
    assert len(result.timeline) >= 2
    assert result.needs_confirmation is False
