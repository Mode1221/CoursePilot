"""배치 수집 대상 상권. 좌표는 상권 중심(대략), 반경은 도보권."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class District:
    name: str
    lat: float
    lng: float
    radius_m: int = 1000
    # LOCALDATA 는 시군구 단위 파일로 배포된다. 폐업 판정을 하려면 이 상권이
    # 속한 시군구 파일이 반드시 있어야 한다(app/batch/coverage.py 가 확인).
    sigungu: str = ""


# 수도권 주요 상권 24곳. 한 곳당 4개 슬롯 × 카테고리 검색으로 전수 수집한다.
#
# 좌표는 대표 역·랜드마크 기준(2026-09 대조). 반경은 도보권이되, 서로 붙어 있는
# 상권(연남-홍대, 을지로-종로-익선동 등)은 같은 원을 두 번 훑지 않도록 줄여 잡았다.
# 겹침 현황은 `python scripts/districts_map.py` 로 확인한다.
DISTRICTS: tuple[District, ...] = (
    District("성수", 37.5445, 127.0557, sigungu="성동구"),
    District("연남", 37.5610, 126.9250, 500, sigungu="마포구"),
    District("홍대", 37.5563, 126.9236, 700, sigungu="마포구"),
    District("합정", 37.5495, 126.9137, 600, sigungu="마포구"),
    District("망원", 37.5560, 126.9105, 700, sigungu="마포구"),
    District("이태원", 37.5345, 126.9946, 700, sigungu="용산구"),
    District("한남", 37.5340, 127.0016, 600, sigungu="용산구"),
    District("을지로", 37.5660, 126.9910, 600, sigungu="중구"),
    District("종로", 37.5704, 126.9920, 600, sigungu="종로구"),
    District("익선동", 37.5740, 126.9900, 450, sigungu="종로구"),
    District("서촌", 37.5790, 126.9700, 800, sigungu="종로구"),
    District("북촌", 37.5826, 126.9830, 700, sigungu="종로구"),
    District("강남역", 37.4979, 127.0276, sigungu="강남구"),
    District("신사", 37.5163, 127.0203, sigungu="강남구"),
    District("압구정", 37.5271, 127.0286, sigungu="강남구"),
    District("청담", 37.5194, 127.0533, 800, sigungu="강남구"),
    District("삼성", 37.5089, 127.0631, sigungu="강남구"),
    District("여의도", 37.5216, 126.9243, sigungu="영등포구"),
    District("영등포", 37.5160, 126.9070, sigungu="영등포구"),
    District("건대", 37.5405, 127.0700, sigungu="광진구"),
    District("잠실", 37.5133, 127.1000, sigungu="송파구"),
    District("신촌", 37.5556, 126.9368, 700, sigungu="서대문구"),
    District("대학로", 37.5820, 127.0020, 800, sigungu="종로구"),
    District("판교", 37.3947, 127.1112, sigungu="분당구"),
)
