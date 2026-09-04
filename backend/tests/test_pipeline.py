from datetime import time

import pytest

from app.adapters.map_service import MockMapService
from app.pipeline.agent import generate_course
from app.pipeline.decomposition import parse_constraints
from app.pipeline.validation import is_open_at
from app.schemas import Place, TravelMode


def test_parse_constraints():
    c = parse_constraints("토요일 오후 1시 성수동, 3시간짜리 코스, 도보 10분 이내, 조용한 곳, 예산 5만원")
    assert c.region == "성수동"
    assert c.start_time == time(13, 0)
    assert c.duration_min == 180
    assert c.travel_mode == TravelMode.WALK
    assert c.max_travel_min == 10
    assert c.budget_max == 50_000
    assert "조용한" in c.keywords


def test_is_open_at_break_time():
    p = Place(
        id="x", name="x", lat=0, lng=0,
        open_time=time(10, 0), close_time=time(22, 0),
        break_start=time(15, 0), break_end=time(17, 0),
    )
    assert is_open_at(p, time(14, 0))
    assert not is_open_at(p, time(16, 0))  # 브레이크
    assert not is_open_at(p, time(9, 0))   # 개점 전


@pytest.mark.asyncio
async def test_generate_course_returns_timeline():
    result = await generate_course("성수동 오전 10시 5시간 코스", MockMapService())
    assert len(result.timeline) >= 3
    # 넉넉한 시간창 + 이동 상한 없음 → 완화/확인 불필요
    assert result.needs_confirmation is False
    # 모든 장소가 도착 시각에 영업 중이어야 함 (검증 통과)
    for item in result.timeline:
        assert item.arrive is not None
