"""장소 원탭 별점(자체 명시 신호, data #9).

방문 후 ⭐ 1~5만 받음(텍스트 없음 → 광고·약관 무관). 합/개수로 평균 집계해
planner 스코어에 자체 정량 신호로 반영. DB/인메모리 폴백.
"""
from __future__ import annotations

from collections import defaultdict


class RatingStore:
    def __init__(self) -> None:
        self._mem: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))  # (sum, count)

    def submit(self, place_id: str, stars: int, replaces: int | None = None) -> None:
        """별점 반영. replaces 가 있으면 같은 사람의 이전 별점을 대체한다
        (합만 조정하고 표본 수는 늘리지 않는다 → 반복 제출로 평균을 못 흔든다)."""
        if replaces is not None:
            self._replace(place_id, stars, replaces)
            return
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

    def _replace(self, place_id: str, stars: int, previous: int) -> None:
        delta = stars - previous
        if self._db_ready():
            from sqlalchemy import text as sql

            from app.db import SessionLocal

            with SessionLocal() as s:
                s.execute(
                    sql(
                        "UPDATE place_ratings SET sum = sum + :d WHERE place_id = :pid"
                    ),
                    {"d": delta, "pid": place_id},
                )
                s.commit()
            return
        cur_sum, cur_cnt = self._mem[place_id]
        self._mem[place_id] = (cur_sum + delta, cur_cnt or 1)

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


class UserRatingStore:
    """사용자가 어떤 장소에 몇 점을 줬는지 기억한다(중복 제출 방지·수정 지원)."""

    MAX_ENTRIES = 100_000

    def __init__(self) -> None:
        self._mem: dict[tuple[str, str], int] = {}

    def previous(self, user_id: str, place_id: str) -> int | None:
        return self._mem.get((user_id, place_id))

    def remember(self, user_id: str, place_id: str, stars: int) -> None:
        if len(self._mem) >= self.MAX_ENTRIES:
            self._mem.pop(next(iter(self._mem)))
        self._mem[(user_id, place_id)] = stars

    def clear(self) -> None:
        self._mem.clear()


user_rating_store = UserRatingStore()
