"""키 없이 배치를 리허설하기 위한 합성 장소 공급기.

카카오 키가 오기 전에도 "수집→필터→보강→저장"이 끝까지 도는지, 저장 스키마와
용량이 맞는지 확인할 수 있어야 한다. 카카오 어댑터와 같은 인터페이스로
그럴듯한 후보를 만들어 준다. 실제 데이터가 아니므로 운영에서는 쓰지 않는다.
"""
from __future__ import annotations

import hashlib
from datetime import date, timedelta

from app.adapters.kakao import GROUP_CODE_SLOT, KakaoLocalService
from app.schemas import Place

# 그룹 코드별 세부 카테고리(실제 카카오 표기를 흉내 낸다)
_CATEGORY_NAMES: dict[str, tuple[str, ...]] = {
    "FD6": ("음식점 > 한식 > 육류,고기", "음식점 > 일식 > 스시", "음식점 > 술집 > 요리주점"),
    "CE7": ("음식점 > 카페 > 커피전문점", "음식점 > 카페 > 디저트"),
    "AT4": ("여행 > 관광,명소 > 공원",),
    "CT1": ("문화,예술 > 전시관", "문화,예술 > 공연장"),
}
PLACES_PER_CATEGORY = 12  # 상권×카테고리당 만들 개수


def _digits(seed: str, count: int) -> int:
    return int(hashlib.sha1(seed.encode()).hexdigest()[:count], 16)


class SamplePlaceSource(KakaoLocalService):
    """카카오 대신 합성 후보를 내는 공급기(같은 메서드 시그니처)."""

    def __init__(self, per_category: int = PLACES_PER_CATEGORY) -> None:
        self._per_category = per_category
        self._centers: dict[str, tuple[float, float] | None] = {}

    @property
    def enabled(self) -> bool:
        return True

    async def search_category(
        self, group_code: str, lat: float, lng: float, radius_m: int = 1000, pages: int = 3
    ) -> list[Place]:
        names = _CATEGORY_NAMES.get(group_code.upper(), ("기타",))
        slot = GROUP_CODE_SLOT.get(group_code.upper(), "activity")
        places: list[Place] = []
        for i in range(self._per_category):
            seed = f"{group_code}:{lat:.4f}:{lng:.4f}:{i}"
            category = names[i % len(names)]
            # 좌표는 상권 중심에서 반경 안으로 흩는다(동선 계산이 의미를 갖도록)
            offset = (_digits(seed, 4) % 200 - 100) / 100_000 * (radius_m / 1000)
            places.append(
                Place(
                    id=f"sample-{_digits(seed, 10)}",
                    name=f"{slot}{i + 1}호점",
                    category=category,
                    category_code=group_code.upper(),
                    address=f"샘플로 {i + 1}",
                    lat=lat + offset,
                    lng=lng + offset,
                    opened_on=date.today() - timedelta(days=365 * (i % 15)),
                )
            )
        return places

    async def search_places(
        self, region: str, keywords: list[str], limit: int = 10
    ) -> list[Place]:
        found = await self.search_category("FD6", 37.5445, 127.0557)
        return found[:limit]
