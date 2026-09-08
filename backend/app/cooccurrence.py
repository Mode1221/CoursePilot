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
        pairs = list(combinations(uniq, 2))
        if not pairs:
            return
        if not self._db_ready():
            for a, b in pairs:
                self._mem[frozenset((a, b))] += weight
            return
        # 쌍마다 커밋하면 장소 수의 제곱만큼 왕복한다 → 한 세션에서 처리
        from app.db import SessionLocal
        from app.models import CooccurrenceModel

        with SessionLocal() as s:
            for a, b in pairs:
                lo, hi = sorted((a, b))
                row = s.get(CooccurrenceModel, (lo, hi))
                if row is None:
                    s.add(CooccurrenceModel(place_a=lo, place_b=hi, count=weight))
                else:
                    row.count += weight
            s.commit()

    def affinity(self, place_id: str, anchors: list[str]) -> float:
        """anchors(이미 담긴 장소들)와 place_id 의 공동 채택 합계."""
        others = [a for a in anchors if a != place_id]
        if not others:
            return 0.0
        if not self._db_ready():
            return sum(self._mem.get(frozenset((place_id, a)), 0.0) for a in others)
        # 앵커마다 조회하면 후보 수 × 앵커 수만큼 쿼리가 난다 → 한 번에 읽는다
        from sqlalchemy import select, tuple_

        from app.db import SessionLocal
        from app.models import CooccurrenceModel

        keys = [tuple(sorted((place_id, a))) for a in others]
        with SessionLocal() as s:
            rows = s.execute(
                select(CooccurrenceModel.count).where(
                    tuple_(CooccurrenceModel.place_a, CooccurrenceModel.place_b).in_(keys)
                )
            ).all()
        return float(sum(r[0] for r in rows))

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
