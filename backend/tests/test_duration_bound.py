"""시작 시각을 말하지 않아도 소요 시간은 지킨다."""
from app.adapters.map_service import MockMapService
from app.pipeline.agent import generate_course


def _span_min(timeline) -> int:
    first, last = timeline[0].arrive, timeline[-1].depart
    start = first.hour * 60 + first.minute
    end = last.hour * 60 + last.minute
    if end < start:
        end += 24 * 60
    return end - start


async def test_시작_시각_없이_말한_소요_시간도_상한이_된다():
    # 예전에는 종료 시각이 없다는 이유로 "2시간"을 무시하고 8시간짜리를 만들었다
    result = await generate_course("성수동 2시간", MockMapService())
    assert _span_min(result.timeline) <= 120


async def test_개수를_말해도_시간을_넘기지_않는다():
    result = await generate_course("성수동 6곳 2시간", MockMapService())
    assert _span_min(result.timeline) <= 120
    # 요청한 만큼 못 채웠으면 사용자에게 확인을 구한다
    assert result.needs_confirmation is True


async def test_시간을_넉넉히_주면_여러_곳이_들어간다():
    result = await generate_course("성수동 5시간", MockMapService())
    assert len(result.timeline) >= 3
    assert _span_min(result.timeline) <= 300
