import pytest

from app.pipeline.decomposition import parse_constraints
from app.pipeline.llm import _to_constraints, decompose
from app.schemas import TravelMode


def test_to_constraints_overrides_rule_base():
    args = {
        "region": "연남동",
        "duration_min": 240,
        "travel_mode": "car",
        "budget_max": 50000,
        "keywords": ["루프탑"],
        "start_time": "18:30",
    }
    c = _to_constraints(args, "대충 문장")
    assert c.region == "연남동"
    assert c.duration_min == 240
    assert c.travel_mode == TravelMode.CAR
    assert c.budget_max == 50000
    assert c.keywords == ["루프탑"]
    assert c.start_time.hour == 18 and c.start_time.minute == 30


@pytest.mark.asyncio
async def test_decompose_falls_back_without_key():
    # 키 미설정(테스트 환경) → 규칙 기반 결과와 동일해야 함
    text = "성수동 오후 1시 3시간 도보 10분 이내"
    got = await decompose(text)
    expected = parse_constraints(text)
    assert got.region == expected.region == "성수동"
    assert got.start_time == expected.start_time
    assert got.duration_min == expected.duration_min
