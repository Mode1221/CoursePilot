"""시간대 컨텍스트 신호 (data #12).

장소가 어떤 시간대(아침/낮/저녁)에 코스로 채택되는지 누적 → 요청 시간대에 맞는 장소 가점.
예: 브런치 카페는 아침·낮, 바는 저녁에 강함. 콜드스타트에 강하고 광고 무관.
"""
from __future__ import annotations

from collections import defaultdict


def daypart_of(hour: int) -> str:
    if hour < 12:
        return "morning"
    if hour < 18:
        return "afternoon"
    return "evening"


class TimeContextStore:
    def __init__(self) -> None:
        self._mem: dict[tuple[str, str], float] = defaultdict(float)

    def bump(self, place_id: str, daypart: str, weight: float = 1.0) -> None:
        if self._db_ready():
            from app.db import SessionLocal
            from app.models import TimeContextModel

            with SessionLocal() as s:
                row = s.get(TimeContextModel, (place_id, daypart))
                if row is None:
                    s.add(TimeContextModel(place_id=place_id, daypart=daypart, count=weight))
                else:
                    row.count += weight
                s.commit()
            return
        self._mem[(place_id, daypart)] += weight

    def bump_many(self, place_ids: list[str], daypart: str, weight: float = 1.0) -> None:
        """여러 장소를 한 번에 가산. DB 모드에서도 세션·커밋 1회로 처리한다."""
        if not place_ids:
            return
        if not self._db_ready():
            for pid in place_ids:
                self._mem[(pid, daypart)] += weight
            return

        from app.db import SessionLocal
        from app.models import TimeContextModel

        with SessionLocal() as s:
            for pid in place_ids:
                row = s.get(TimeContextModel, (pid, daypart))
                if row is None:
                    s.add(TimeContextModel(place_id=pid, daypart=daypart, count=weight))
                else:
                    row.count += weight
            s.commit()

    def scores(self, place_ids: list[str], daypart: str) -> dict[str, float]:
        if not place_ids:
            return {}
        if self._db_ready():
            from sqlalchemy import select

            from app.db import SessionLocal
            from app.models import TimeContextModel

            with SessionLocal() as s:
                rows = s.execute(
                    select(TimeContextModel.place_id, TimeContextModel.count).where(
                        TimeContextModel.place_id.in_(place_ids),
                        TimeContextModel.daypart == daypart,
                    )
                ).all()
                found = {r[0]: r[1] for r in rows}
        else:
            found = {pid: self._mem.get((pid, daypart), 0.0) for pid in place_ids}
        return {pid: found.get(pid, 0.0) for pid in place_ids}

    @staticmethod
    def _db_ready() -> bool:
        from app.db import is_ready

        return is_ready()


time_context_store = TimeContextStore()
