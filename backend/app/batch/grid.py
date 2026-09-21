"""상권을 작은 원(격자 칸)으로 쪼갠다 — 카카오 질의 상한을 넘기 위해.

카카오 로컬 API 는 질의 하나에 최대 45건(15 × 3페이지)만 준다. 반경 1km 를
한 점에서 부르면 음식점이 수천 곳이어도 가까운 45곳에서 끝난다(실측: 24개 상권
3,103건, 상권당 100~165건). 그래서 상권 원을 겹치는 작은 원들로 덮고 원마다
부른 뒤 id 로 합친다.

정사각 격자 간격 s 로 놓은 반지름 r 의 원들이 빈틈 없이 덮이려면 r ≥ s/√2 다.
r=300m, s=400m 는 그 조건을 만족하면서(300 ≥ 283) 겹침이 과하지 않다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.batch.districts import District

CELL_RADIUS_M = 300  # 칸 하나의 검색 반경
CELL_STEP_M = 400  # 칸 중심 간격(≤ r·√2 여야 빈틈이 없다)
_M_PER_DEG_LAT = 111_320.0


@dataclass(frozen=True)
class Cell:
    """상권 안의 검색 칸. key 는 진행 상태 저장용(재실행 시 건너뛰기)."""

    lat: float
    lng: float
    radius_m: int
    key: str


def cells_for(
    district: District,
    *,
    cell_radius_m: int = CELL_RADIUS_M,
    step_m: int = CELL_STEP_M,
) -> list[Cell]:
    """상권 원(중심·반경)을 덮는 칸 목록. 작은 상권은 칸 하나로 끝난다.

    칸 중심이 상권 원 밖이면 버린다 — 안쪽 칸들이 이미 원 경계 너머 칸 반경만큼
    덮으므로, 밖의 칸까지 부르면 옆 상권을 한 번 더 훑고 상권 밖 장소를 끌어온다.
    """
    radius = district.radius_m
    if radius <= cell_radius_m:
        return [Cell(district.lat, district.lng, radius, "c0")]
    m_per_deg_lng = _M_PER_DEG_LAT * math.cos(math.radians(district.lat))
    n = math.ceil(radius / step_m)
    cells: list[Cell] = []
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            dy, dx = i * step_m, j * step_m
            if math.hypot(dx, dy) > radius:
                continue
            cells.append(
                Cell(
                    lat=district.lat + dy / _M_PER_DEG_LAT,
                    lng=district.lng + dx / m_per_deg_lng,
                    radius_m=cell_radius_m,
                    key=f"g{i:+d}{j:+d}",
                )
            )
    return cells
