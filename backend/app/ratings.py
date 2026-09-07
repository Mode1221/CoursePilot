"""장소 원탭 별점(자체 명시 신호, data #9).

방문 후 ⭐ 1~5만 받음(텍스트 없음 → 광고·약관 무관). 합/개수로 평균 집계해
planner 스코어에 자체 정량 신호로 반영. DB/인메모리 폴백.
"""
from __future__ import annotations

from collections import defaultdict


class RatingStore:
    def __init__(self) -> None:
        self._mem: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))  # (sum, count)

    def submit(self, place_id: str, stars: int) -> None:
        if self._db_ready():
            from sqlalchemy import text as sql

            from app.db import SessionLocal

            with SessionLocal() as s:
                s.execute(
                    sql(
                        "INSERT INTO place_ratings (place_id, sum, count) VALUES (:pid, :st, 1) "
                        "ON CONFLICT (place_id) DO UPDATE SET "
                        "sum = place_ratings.sum + :st, count = place_ratings.count + 1"
                    ),
                    {"pid": place_id, "st": stars},
                )
                s.commit()
            return
        cur_sum, cur_cnt = self._mem[place_id]
        self._mem[place_id] = (cur_sum + stars, cur_cnt + 1)

    def averages(self, place_ids: list[str]) -> dict[str, float]:
        """place_id별 평균 별점(없으면 미포함)."""
        if not place_ids:
            return {}
        if self._db_ready():
            from sqlalchemy import select

            from app.db import SessionLocal
            from app.models import PlaceRatingModel

            with SessionLocal() as s:
                rows = s.execute(
                    select(
                        PlaceRatingModel.place_id,
                        PlaceRatingModel.sum,
                        PlaceRatingModel.count,
                    ).where(PlaceRatingModel.place_id.in_(place_ids))
                ).all()
                return {r[0]: r[1] / r[2] for r in rows if r[2]}
        out: dict[str, float] = {}
        for pid in place_ids:
            s_sum, s_cnt = self._mem.get(pid, (0, 0))
            if s_cnt:
                out[pid] = s_sum / s_cnt
        return out

    @staticmethod
    def _db_ready() -> bool:
        from app.db import is_ready

        return is_ready()


rating_store = RatingStore()
