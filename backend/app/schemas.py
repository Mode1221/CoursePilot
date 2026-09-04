"""코스/장소/타임라인 도메인 스키마."""
from __future__ import annotations

from datetime import time
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TravelMode(str, Enum):
    WALK = "walk"
    CAR = "car"
    TRANSIT = "transit"


class Place(BaseModel):
    """장소 API 어댑터가 반환하는 정규화된 장소."""

    id: str
    name: str
    category: Optional[str] = None
    address: Optional[str] = None
    lat: float
    lng: float
    rating: Optional[float] = None
    open_time: Optional[time] = None
    close_time: Optional[time] = None
    break_start: Optional[time] = None
    break_end: Optional[time] = None


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
    arrive: Optional[time] = None
    depart: Optional[time] = None
    travel_to_next: Optional[Route] = None


class Course(BaseModel):
    """공유/저장되는 코스 상태(Single Source of Truth)."""

    id: str
    title: str = "새 코스"
    region: Optional[str] = None
    items: list[TimelineItem] = Field(default_factory=list)
    locked: bool = False


class PlanConstraints(BaseModel):
    """자연어에서 분해된 조건(7-1 Decomposition 결과)."""

    region: Optional[str] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    duration_min: Optional[int] = None
    max_travel_min: Optional[int] = None
    travel_mode: TravelMode = TravelMode.WALK
    budget_max: Optional[int] = None  # 하드 제약
    keywords: list[str] = Field(default_factory=list)  # 조용한, 비건 등 소프트 제약
