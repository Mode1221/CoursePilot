"""배치 수집 대상 상권. 좌표는 상권 중심(대략), 반경은 도보권."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class District:
    name: str
    lat: float
    lng: float
    radius_m: int = 1000
    # LOCALDATA 적재·커버리지 판정에 쓴다. 시군구 이름만으로는 부족하다 —
    # "중구"는 부산·대구·인천에도 있어서 시도까지 함께 봐야 한다.
    sigungu: str = ""
    sido: str = "서울특별시"


# 수도권 주요 상권 36곳(서울 35 + 판교). 2026-09-28 서울 12곳 추가 — 16개 구. 한 곳당 4개 슬롯 × 카테고리 검색으로 전수 수집한다.
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
    # 2026-09-28 추가 — 서울 먼저 공개하면서 11개 구만 덮던 것을 16개 구로
    District("사당", 37.4765, 126.9816, 700, sigungu="동작구"),
    District("샤로수길", 37.4800, 126.9530, 600, sigungu="관악구"),
    District("문래", 37.5170, 126.8950, 500, sigungu="영등포구"),
    District("용리단길", 37.5320, 126.9705, 600, sigungu="용산구"),
    District("서울숲", 37.5460, 127.0420, 600, sigungu="성동구"),
    District("노원", 37.6557, 127.0615, 800, sigungu="노원구"),
    District("목동", 37.5265, 126.8730, 800, sigungu="양천구"),
    District("연희동", 37.5665, 126.9300, 500, sigungu="서대문구"),
    District("성신여대", 37.5927, 127.0164, 600, sigungu="성북구"),
    District("왕십리", 37.5612, 127.0377, 600, sigungu="성동구"),
    District("명동", 37.5630, 126.9852, 450, sigungu="중구"),
    District("광화문", 37.5711, 126.9766, 600, sigungu="종로구"),
    District("판교", 37.3947, 127.1112, sigungu="분당구", sido="경기도"),
)
