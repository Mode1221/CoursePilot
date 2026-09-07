"""장소 인기(암묵적 정량 신호) 집계.

리뷰 입력 없이 사용 행동만으로 쌓이는 신호 → 콜드스타트에 강함.
- 코스에 채택될 때마다 adopt(+1)
- 북마크된 코스에 등장하면 가중(+2)
planner 스코어에 정량 가점으로 반영. DB/인메모리 폴백.
"""
from __future__ import annotations

from collections import defaultdict


class PopularityStore:
    def __init__(self) -> None:
        self._mem: dict[str, int] = defaultdict(int)

    def bump(self, place_id: str, weight: int = 1) -> None:
        if self._db_ready():
            from sqlalchemy import text as sql

            from app.db import SessionLocal

            with SessionLocal() as s:
                # upsert: 없으면 삽입, 있으면 누적
                s.execute(
                    sql(
                        "INSERT INTO place_popularity (place_id, score) VALUES (:pid, :w) "
                        "ON CONFLICT (place_id) DO UPDATE SET score = place_popularity.score + :w"
                    ),
                    {"pid": place_id, "w": weight},
                )
                s.commit()
            return
        self._mem[place_id] += weight

    def bump_many(self, place_ids: list[str], weight: int = 1) -> None:
        for pid in place_ids:
            self.bump(pid, weight)

    def scores(self, place_ids: list[str]) -> dict[str, int]:
        """요청한 place_id 들의 인기 점수(없으면 0)."""
        if not place_ids:
            return {}
        if self._db_ready():
            from sqlalchemy import select

            from app.db import SessionLocal
            from app.models import PopularityModel

            with SessionLocal() as s:
                rows = s.execute(
                    select(PopularityModel.place_id, PopularityModel.score).where(
                        PopularityModel.place_id.in_(place_ids)
                    )
                ).all()
                found = {r[0]: r[1] for r in rows}
        else:
            found = {pid: self._mem[pid] for pid in place_ids if pid in self._mem}
        return {pid: found.get(pid, 0) for pid in place_ids}

    @staticmethod
    def _db_ready() -> bool:
        from app.db import is_ready

        return is_ready()


popularity_store = PopularityStore()
