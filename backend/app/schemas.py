"""코스/장소/타임라인 도메인 스키마."""
from __future__ import annotations

from datetime import time
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
    locked: bool = False


class PlanConstraints(BaseModel):
    """자연어에서 분해된 조건(7-1 Decomposition 결과)."""

    region: str | None = None
    start_time: time | None = None
    end_time: time | None = None
    duration_min: int | None = None
    max_travel_min: int | None = None
    travel_mode: TravelMode = TravelMode.WALK
    budget_max: int | None = None  # 하드 제약
    keywords: list[str] = Field(default_factory=list)  # 조용한, 비건 등 소프트 제약
