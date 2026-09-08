"""코스/장소/타임라인 도메인 스키마."""
from __future__ import annotations

from datetime import date, time
from enum import Enum

from pydantic import BaseModel, Field


class TravelMode(str, Enum):
    WALK = "walk"
    CAR = "car"
    TRANSIT = "transit"


class Place(BaseModel):
    """장소 API 어댑터가 반환하는 정규화된 장소."""

    id: str
    name: str
    category: str | None = None
    address: str | None = None
    lat: float
    lng: float
    rating: float | None = None
    price: int | None = None  # 1인 예상 비용(원). 없으면 예산 검증에서 제외
    open_time: time | None = None
    close_time: time | None = None
    break_start: time | None = None
    break_end: time | None = None


class Route(BaseModel):
    """A→B 이동 정보."""

    from_place_id: str
    to_place_id: str
    mode: TravelMode
    duration_min: int
    distance_m: int


class TimelineItem(BaseModel):
    """타임라인 한 칸: 장소 + 도착/출발 시각 + 다음 장소로의 이동."""

    place: Place
    arrive: time | None = None
    depart: time | None = None
    travel_to_next: Route | None = None


class Course(BaseModel):
    """공유/저장되는 코스 상태(Single Source of Truth)."""

    id: str
    title: str = "새 코스"
    region: str | None = None
    owner_id: str | None = None  # 생성자(로그인 회원) id
    items: list[TimelineItem] = Field(default_factory=list)
    plan_date: date | None = None  # 모임 날짜(캘린더 내보내기 기준일)
    party_size: int | None = None  # 인원수(요약·공유 텍스트 표시용)
    locked: bool = False
    predicted_score: float | None = None  # 생성 시 코스 목적함수 점수(#17 만족도 대조용)


class PlanConstraints(BaseModel):
    """자연어에서 분해된 조건(7-1 Decomposition 결과)."""

    region: str | None = None
    start_place: str | None = None  # 출발지("강남역에서 출발")
    start_time: time | None = None
    end_time: time | None = None
    duration_min: int | None = None
    max_travel_min: int | None = None
    travel_mode: TravelMode = TravelMode.WALK
    strict_travel_mode: bool = False  # "도보로만" 처럼 수단 고정을 요청한 경우
    budget_max: int | None = None  # 하드 제약
    party_size: int | None = None  # 인원수
    plan_date: date | None = None  # 모임 날짜("내일", "이번 주 토요일")
    stop_count: int | None = None  # 방문할 장소 개수("2차", "세 군데")
    companion: str | None = None  # 동행유형: 데이트/친구/가족/회식/혼자 (컨텍스트 신호)
    keywords: list[str] = Field(default_factory=list)  # 조용한, 비건 등 소프트 제약
    exclude_keywords: list[str] = Field(default_factory=list)  # "술집 빼고" 같은 제외 조건
