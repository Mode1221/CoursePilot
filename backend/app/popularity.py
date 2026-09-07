"""장소 인기(암묵적 정량 신호) 집계 — 시간 감쇠 EWMA.

리뷰 입력 없이 사용 행동만으로 쌓이는 신호(콜드스타트에 강함).
- 코스 채택 +1, 북마크 +2, 사용자 거부(-1)
- 최근 신호에 가중: 누적값을 마지막 갱신 이후 경과에 따라 반감기로 감쇠 후 가산(EWMA 근사)
정규화는 planner 에서 지역×카테고리 그룹 기준 상대값으로 수행.
"""
from __future__ import annotations

import time as _time
from collections import defaultdict

HALF_LIFE_DAYS = 30.0
_HALF_LIFE_SEC = HALF_LIFE_DAYS * 86400


def _decay(elapsed_sec: float) -> float:
    return 0.5 ** (elapsed_sec / _HALF_LIFE_SEC)


class PopularityStore:
    def __init__(self) -> None:
        # place_id -> (score, last_ts)
        self._mem: dict[str, tuple[float, float]] = defaultdict(lambda: (0.0, 0.0))

    def bump(self, place_id: str, weight: float = 1) -> None:
        now = _time.time()
        if self._db_ready():
            from app.db import SessionLocal
            from app.models import PopularityModel

            with SessionLocal() as s:
                row = s.get(PopularityModel, place_id)
                if row is None:
                    from app.models import PopularityModel as PM

                    s.add(PM(place_id=place_id, score=float(weight), updated_at=now))
                else:
                    row.score = row.score * _decay(now - row.updated_at) + weight
                    row.updated_at = now
                s.commit()
            return
        cur, ts = self._mem[place_id]
        self._mem[place_id] = (cur * _decay(now - ts) + weight if ts else float(weight), now)

    def bump_many(self, place_ids: list[str], weight: float = 1) -> None:
        for pid in place_ids:
            self.bump(pid, weight)

    def scores(self, place_ids: list[str]) -> dict[str, float]:
        """요청한 place_id 들의 현재 인기(읽는 시점까지 감쇠 적용). 없으면 0."""
        if not place_ids:
            return {}
        now = _time.time()
        if self._db_ready():
            from sqlalchemy import select

            from app.db import SessionLocal
            from app.models import PopularityModel

            with SessionLocal() as s:
                rows = s.execute(
                    select(
                        PopularityModel.place_id,
                        PopularityModel.score,
                        PopularityModel.updated_at,
                    ).where(PopularityModel.place_id.in_(place_ids))
                ).all()
                found = {r[0]: r[1] * _decay(now - r[2]) for r in rows}
        else:
            found = {}
            for pid in place_ids:
                if pid in self._mem:
                    sc, ts = self._mem[pid]
                    found[pid] = sc * _decay(now - ts) if ts else 0.0
        return {pid: found.get(pid, 0.0) for pid in place_ids}

    @staticmethod
    def _db_ready() -> bool:
        from app.db import is_ready

        return is_ready()


popularity_store = PopularityStore()
