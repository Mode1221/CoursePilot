"""경량 협업 필터링 — 장소 공동 채택(co-occurrence) (활용).

같은 코스에 함께 채택된 장소 쌍을 누적한다. "A를 좋아한 코스는 B도 함께 담더라"
라는 아이템-아이템 신호로, 후보에 이미 담긴 장소와 잘 어울리는 장소를 가점.
콜드스타트에 강하고(행동만으로 축적) 광고 무관.
"""
from __future__ import annotations

from collections import defaultdict
from itertools import combinations


class CooccurrenceStore:
    def __init__(self) -> None:
        # frozenset({a,b}) -> count
        self._mem: dict[frozenset[str], float] = defaultdict(float)

    def bump_course(self, place_ids: list[str], weight: float = 1.0) -> None:
        """코스에 함께 담긴 장소 쌍을 모두 가중 누적."""
        uniq = list(dict.fromkeys(place_ids))  # 중복 제거·순서 유지
        for a, b in combinations(uniq, 2):
            self._add(a, b, weight)

    def _add(self, a: str, b: str, weight: float) -> None:
        if self._db_ready():
            from app.db import SessionLocal
            from app.models import CooccurrenceModel

            lo, hi = sorted((a, b))
            with SessionLocal() as s:
                row = s.get(CooccurrenceModel, (lo, hi))
                if row is None:
                    s.add(CooccurrenceModel(place_a=lo, place_b=hi, count=weight))
                else:
                    row.count += weight
                s.commit()
            return
        self._mem[frozenset((a, b))] += weight

    def affinity(self, place_id: str, anchors: list[str]) -> float:
        """anchors(이미 담긴 장소들)와 place_id 의 공동 채택 합계."""
        return sum(self._pair(place_id, a) for a in anchors if a != place_id)

    def _pair(self, a: str, b: str) -> float:
        if self._db_ready():
            from app.db import SessionLocal
            from app.models import CooccurrenceModel

            lo, hi = sorted((a, b))
            with SessionLocal() as s:
                row = s.get(CooccurrenceModel, (lo, hi))
                return row.count if row else 0.0
        return self._mem.get(frozenset((a, b)), 0.0)

    def top_partners(self, place_id: str, k: int = 5) -> list[tuple[str, float]]:
        """place_id 와 가장 자주 함께 채택된 장소 상위 k (id, count) 내림차순."""
        if self._db_ready():
            from sqlalchemy import or_, select

            from app.db import SessionLocal
            from app.models import CooccurrenceModel

            with SessionLocal() as s:
                rows = s.execute(
                    select(
                        CooccurrenceModel.place_a,
                        CooccurrenceModel.place_b,
                        CooccurrenceModel.count,
                    ).where(
                        or_(
                            CooccurrenceModel.place_a == place_id,
                            CooccurrenceModel.place_b == place_id,
                        )
                    )
                ).all()
            pairs = [
                (a if b == place_id else b, c) for a, b, c in rows if place_id in (a, b)
            ]
        else:
            pairs = [
                (next(iter(key - {place_id})), c)
                for key, c in self._mem.items()
                if place_id in key and len(key) == 2
            ]
        pairs.sort(key=lambda x: x[1], reverse=True)
        return pairs[:k]

    @staticmethod
    def _db_ready() -> bool:
        from app.db import is_ready

        return is_ready()


cooccurrence_store = CooccurrenceStore()
