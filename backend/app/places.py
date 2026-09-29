"""전역 장소 저장소.

코스에 등장한 장소의 정규화 스냅샷을 보관해, 협업 필터링 추천 등에서 id→장소
복원을 가능케 한다(어댑터는 지역 검색만 제공하므로 id 단건 조회 대체). DB/인메모리 폴백.
"""
from __future__ import annotations

import math

from app.schemas import Place

# 인메모리 폴백은 개발/비상용이므로 보관 수에 상한을 둔다(무한 증가 방지)
MAX_MEM_PLACES = 2000


class PlaceRepository:
    def __init__(self) -> None:
        self._mem: dict[str, Place] = {}

    def upsert_many(self, places: list[Place]) -> None:
        if self._db_ready():
            from app.db import SessionLocal
            from app.models import PlaceModel

            with SessionLocal() as s:
                for p in places:
                    row = s.get(PlaceModel, p.id)
                    data = p.model_dump(mode="json")
                    if row is None:
                        s.add(PlaceModel(id=p.id, data=data))
                    else:
                        row.data = data
                s.commit()
            return
        for p in places:
            self._mem.pop(p.id, None)  # 최근 사용 순서를 유지하도록 다시 넣는다
            self._mem[p.id] = p
        while len(self._mem) > MAX_MEM_PLACES:
            self._mem.pop(next(iter(self._mem)))  # 가장 오래된 것부터 버린다

    def get_many(self, ids: list[str]) -> dict[str, Place]:
        if not ids:
            return {}
        if self._db_ready():
            from sqlalchemy import select

            from app.db import SessionLocal
            from app.models import PlaceModel

            with SessionLocal() as s:
                rows = s.execute(
                    select(PlaceModel.id, PlaceModel.data).where(PlaceModel.id.in_(ids))
                ).all()
                return {r[0]: Place(**r[1]) for r in rows}
        return {pid: self._mem[pid] for pid in ids if pid in self._mem}

    def delete_many(self, ids: list[str]) -> int:
        """폐업 등으로 더 이상 추천하면 안 되는 장소를 스냅샷에서 지운다."""
        if not ids:
            return 0
        if self._db_ready():
            from app.db import SessionLocal
            from app.models import PlaceModel

            removed = 0
            with SessionLocal() as s:
                for pid in ids:
                    row = s.get(PlaceModel, pid)
                    if row is not None:
                        s.delete(row)
                        removed += 1
                s.commit()
            return removed
        return sum(1 for pid in ids if self._mem.pop(pid, None) is not None)

    def all(self, limit: int = 500) -> list[Place]:
        """저장된 장소 스냅샷(최대 limit). 콜드스타트 추천 폴백용."""
        if self._db_ready():
            from sqlalchemy import select

            from app.db import SessionLocal
            from app.models import PlaceModel

            with SessionLocal() as s:
                rows = s.execute(select(PlaceModel.data).limit(limit)).all()
                return [Place(**r[0]) for r in rows]
        return list(self._mem.values())[-limit:]  # 최근 것 위주

    def near(self, lat: float, lng: float, radius_m: int, limit: int = 3000) -> list[Place]:
        """좌표 반경 안의 저장 장소(사각 범위로 먼저 거른 뒤 거리로 자른다). 코스 후보 풀용."""
        dlat = radius_m / 111_000
        dlng = radius_m / (111_000 * max(0.2, math.cos(math.radians(lat))))
        if self._db_ready():
            from sqlalchemy import select

            from app.db import SessionLocal
            from app.models import PlaceModel

            with SessionLocal() as s:
                plat, plng = _lat_lng_exprs(s)
                rows = s.execute(
                    select(PlaceModel.data)
                    .where(plat.between(lat - dlat, lat + dlat), plng.between(lng - dlng, lng + dlng))
                    .limit(limit)
                ).all()
                boxed = [Place(**r[0]) for r in rows]
        else:
            boxed = [
                p for p in self._mem.values()
                if abs(p.lat - lat) <= dlat and abs(p.lng - lng) <= dlng
            ][:limit]
        return [p for p in boxed if _approx_m(lat, lng, p.lat, p.lng) <= radius_m]

    @staticmethod
    def _db_ready() -> bool:
        from app.db import is_ready

        return is_ready()


def _lat_lng_exprs(session):
    """좌표 비교식. Postgres 에서는 키를 **SQL 리터럴**로 박아 표현식 인덱스(db.py)를 타게 한다.

    SQLAlchemy 기본 JSON 경로는 키를 바인드 파라미터로 보내 인덱스 식과 모양이 달라진다 —
    그러면 저장 장소 1.8만 건 JSON 을 매번 전부 풀어 보는 전체 스캔이 된다.
    """
    from sqlalchemy import Float, cast, literal_column

    from app.models import PlaceModel

    if session.bind.dialect.name == "postgresql":
        return (
            cast(literal_column("places.data ->> 'lat'"), Float),
            cast(literal_column("places.data ->> 'lng'"), Float),
        )
    return PlaceModel.data["lat"].as_float(), PlaceModel.data["lng"].as_float()


def _approx_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """도보권(수 km) 거리 근사 — 등장방형 투영이면 충분하다."""
    x = (lng2 - lng1) * 111_000 * math.cos(math.radians((lat1 + lat2) / 2))
    y = (lat2 - lat1) * 111_000
    return math.hypot(x, y)


place_repo = PlaceRepository()
