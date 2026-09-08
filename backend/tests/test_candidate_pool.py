from app.pipeline.agent import CANDIDATES_PER_SLOT, MAX_CANDIDATES, _attempt
from app.schemas import Place, PlanConstraints


class RecordingMapService:
    def __init__(self):
        self.limits: list[int] = []

    async def search_places(self, region, keywords, limit=10):
        self.limits.append(limit)
        return [
            Place(id=f"p{i}", name=f"place {i}", category="cafe", lat=37.5, lng=127.0)
            for i in range(limit)
        ]

    async def get_route(self, origin, dest, mode):
        raise AssertionError("경로 계산까지 갈 필요 없는 테스트")


async def test_pool_scales_with_slots():
    svc = RecordingMapService()
    try:
        await _attempt(PlanConstraints(duration_min=360), svc)
    except Exception:
        pass  # 후보 수집 이후 단계는 이 테스트의 관심사가 아니다
    assert svc.limits
    assert svc.limits[0] >= 4 * CANDIDATES_PER_SLOT
    assert svc.limits[0] <= MAX_CANDIDATES
