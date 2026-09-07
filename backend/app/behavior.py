"""행동 선호 학습 — 선언 선호 vs 행동 선호 보정 (data #13).

온보딩에서 선언한 선호(prefs.mood 등)와 별개로, 사용자가 실제로 채택/유지하는
카테고리를 누적해 개인화에 반영한다. 선언과 행동이 어긋나면 행동을 신뢰.
콜드스타트: 초기엔 데이터 없어 무영향, 사용할수록 정밀해짐.
"""
from __future__ import annotations

from collections import defaultdict


class BehaviorStore:
    def __init__(self) -> None:
        # user_id -> {category: count}
        self._mem: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

    def bump(self, user_id: str, categories: list[str], weight: float = 1.0) -> None:
        if not user_id:
            return
        if self._db_ready():
            from app.db import SessionLocal
            from app.models import BehaviorModel

            with SessionLocal() as s:
                for cat in categories:
                    row = s.get(BehaviorModel, (user_id, cat))
                    if row is None:
                        s.add(BehaviorModel(user_id=user_id, category=cat, count=weight))
                    else:
                        row.count += weight
                s.commit()
            return
        for cat in categories:
            self._mem[user_id][cat] += weight

    def top_categories(self, user_id: str, k: int = 2, min_count: float = 2.0) -> list[str]:
        """행동상 선호가 뚜렷한(누적 min_count 이상) 상위 카테고리."""
        if not user_id:
            return []
        counts = self._counts(user_id)
        ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
        return [cat for cat, c in ranked[:k] if c >= min_count]

    def _counts(self, user_id: str) -> dict[str, float]:
        if self._db_ready():
            from sqlalchemy import select

            from app.db import SessionLocal
            from app.models import BehaviorModel

            with SessionLocal() as s:
                rows = s.execute(
                    select(BehaviorModel.category, BehaviorModel.count).where(
                        BehaviorModel.user_id == user_id
                    )
                ).all()
                return {r[0]: r[1] for r in rows}
        return dict(self._mem.get(user_id, {}))

    @staticmethod
    def _db_ready() -> bool:
        from app.db import is_ready

        return is_ready()


behavior_store = BehaviorStore()
