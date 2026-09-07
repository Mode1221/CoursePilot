"""Best-of-N 시드 전략 선택 로깅 (data #15).

plan_course 의 후보 시드(template/route/sequence/score) 중 코스 점수로 채택된
전략을 누적한다. 어떤 시딩이 좋은 코스를 만드는지 → 목적함수 가중치 튜닝 근거.
"""
from __future__ import annotations

from collections import defaultdict


class StrategyStore:
    def __init__(self) -> None:
        self._mem: dict[str, int] = defaultdict(int)

    def bump(self, label: str, weight: int = 1) -> None:
        if self._db_ready():
            from app.db import SessionLocal
            from app.models import StrategyModel

            with SessionLocal() as s:
                row = s.get(StrategyModel, label)
                if row is None:
                    s.add(StrategyModel(label=label, count=weight))
                else:
                    row.count += weight
                s.commit()
            return
        self._mem[label] += weight

    def counts(self) -> dict[str, int]:
        if self._db_ready():
            from sqlalchemy import select

            from app.db import SessionLocal
            from app.models import StrategyModel

            with SessionLocal() as s:
                rows = s.execute(select(StrategyModel.label, StrategyModel.count)).all()
                return {r[0]: r[1] for r in rows}
        return dict(self._mem)

    @staticmethod
    def _db_ready() -> bool:
        from app.db import is_ready

        return is_ready()


strategy_store = StrategyStore()
