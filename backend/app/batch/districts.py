"""배치 수집 대상 상권. 좌표는 상권 중심(대략), 반경은 도보권."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class District:
    name: str
    lat: float
    lng: float
    radius_m: int = 1000


# 수도권 주요 상권 24곳. 한 곳당 4개 슬롯 × 카테고리 검색으로 전수 수집한다.
DISTRICTS: tuple[District, ...] = (
    District("성수", 37.5445, 127.0557),
    District("연남", 37.5610, 126.9250),
    District("홍대", 37.5563, 126.9236),
    District("합정", 37.5495, 126.9137),
    District("망원", 37.5559, 126.9016),
    District("이태원", 37.5345, 126.9946),
    District("한남", 37.5340, 127.0016),
    District("을지로", 37.5660, 126.9910),
    District("종로", 37.5704, 126.9920),
    District("익선동", 37.5740, 126.9900, 600),
    District("서촌", 37.5790, 126.9700, 800),
    District("북촌", 37.5826, 126.9830, 800),
    District("강남역", 37.4979, 127.0276),
    District("신사", 37.5163, 127.0203),
    District("압구정", 37.5271, 127.0286),
    District("청담", 37.5240, 127.0530),
    District("삼성", 37.5140, 127.0560),
    District("여의도", 37.5216, 126.9243),
    District("영등포", 37.5160, 126.9070),
    District("건대", 37.5405, 127.0700),
    District("잠실", 37.5133, 127.1000),
    District("신촌", 37.5556, 126.9368),
    District("대학로", 37.5820, 127.0020),
    District("판교", 37.3947, 127.1112),
)
