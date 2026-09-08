"""전역 장소 저장소.

코스에 등장한 장소의 정규화 스냅샷을 보관해, 협업 필터링 추천 등에서 id→장소
복원을 가능케 한다(어댑터는 지역 검색만 제공하므로 id 단건 조회 대체). DB/인메모리 폴백.
"""
from __future__ import annotations

from app.schemas import Place


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
            self._mem[p.id] = p

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

    def all(self, limit: int = 500) -> list[Place]:
        """저장된 장소 스냅샷(최대 limit). 콜드스타트 추천 폴백용."""
        if self._db_ready():
            from sqlalchemy import select

            from app.db import SessionLocal
            from app.models import PlaceModel

            with SessionLocal() as s:
                rows = s.execute(select(PlaceModel.data).limit(limit)).all()
                return [Place(**r[0]) for r in rows]
        return list(self._mem.values())[:limit]

    @staticmethod
    def _db_ready() -> bool:
        from app.db import is_ready

        return is_ready()


place_repo = PlaceRepository()
