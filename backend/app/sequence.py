"""재정렬 패턴(선호 순서) 학습 — 카테고리 전이 신호 (data #7).

사용자가 수동 재정렬로 확정한 코스의 인접 카테고리 전이(meal→cafe 등)를 누적.
콜드스타트에 강함(사용 행동만으로 축적) · 텍스트 무관(광고 무영향).
planner 가 후보 코스의 순서 선호도를 매길 때 참고한다.
"""
from __future__ import annotations

from collections import defaultdict


class SequenceStore:
    def __init__(self) -> None:
        # (from_cat, to_cat) -> count
        self._mem: dict[tuple[str, str], float] = defaultdict(float)

    def bump_sequence(self, categories: list[str], weight: float = 1.0) -> None:
        """카테고리 나열의 인접 전이를 가중 누적."""
        if self._db_ready():
            from app.db import SessionLocal
            from app.models import SequenceModel

            with SessionLocal() as s:
                for a, b in zip(categories, categories[1:], strict=False):
                    row = s.get(SequenceModel, (a, b))
                    if row is None:
                        s.add(SequenceModel(from_cat=a, to_cat=b, count=weight))
                    else:
                        row.count += weight
                s.commit()
            return
        for a, b in zip(categories, categories[1:], strict=False):
            self._mem[(a, b)] += weight

    def transition(self, a: str, b: str) -> float:
        if self._db_ready():
            from app.db import SessionLocal
            from app.models import SequenceModel

            with SessionLocal() as s:
                row = s.get(SequenceModel, (a, b))
                return row.count if row else 0.0
        return self._mem.get((a, b), 0.0)

    def all_transitions(self) -> dict[tuple[str, str], float]:
        """전이표 전체를 한 번에 읽는다(카테고리 조합은 소수라 통째로 캐시해도 작다)."""
        if self._db_ready():
            from sqlalchemy import select

            from app.db import SessionLocal
            from app.models import SequenceModel

            with SessionLocal() as s:
                rows = s.execute(
                    select(SequenceModel.from_cat, SequenceModel.to_cat, SequenceModel.count)
                ).all()
            return {(r[0], r[1]): r[2] for r in rows}
        return dict(self._mem)

    def sequence_score(self, categories: list[str]) -> float:
        """카테고리 나열의 학습된 선호 순서 점수(인접 전이 합)."""
        table = self.all_transitions()
        return sum(
            table.get((a, b), 0.0) for a, b in zip(categories, categories[1:], strict=False)
        )

    @staticmethod
    def _db_ready() -> bool:
        from app.db import is_ready

        return is_ready()


sequence_store = SequenceStore()
