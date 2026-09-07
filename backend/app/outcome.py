"""코스 점수 vs 실제 만족도 대조 (data #17).

생성 시 예측한 코스 목적함수 점수와 사용자의 완료 후 만족(👍/👎)을 짝지어 누적.
목적함수가 실제 만족을 예측하는지(계수 튜닝 근거)를 위한 데이터.
"""
from __future__ import annotations


class OutcomeStore:
    def __init__(self) -> None:
        # (합계 점수, 개수) 를 만족/불만족별로 유지 → 평균 점수 비교
        self._liked: tuple[float, int] = (0.0, 0)
        self._disliked: tuple[float, int] = (0.0, 0)

    def record(self, predicted_score: float, liked: bool) -> None:
        if self._db_ready():
            from app.db import SessionLocal
            from app.models import OutcomeModel

            with SessionLocal() as s:
                s.add(OutcomeModel(predicted_score=predicted_score, liked=1 if liked else 0))
                s.commit()
            return
        total, n = self._liked if liked else self._disliked
        pair = (total + predicted_score, n + 1)
        if liked:
            self._liked = pair
        else:
            self._disliked = pair

    def separation(self) -> float | None:
        """만족 평균점수 − 불만족 평균점수. 양수면 목적함수가 만족을 잘 예측.

        표본이 양쪽 모두 없으면 None.
        """
        if self._db_ready():
            from sqlalchemy import func, select

            from app.db import SessionLocal
            from app.models import OutcomeModel

            with SessionLocal() as s:
                rows = s.execute(
                    select(
                        OutcomeModel.liked,
                        func.avg(OutcomeModel.predicted_score),
                    ).group_by(OutcomeModel.liked)
                ).all()
                avg = {int(k): v for k, v in rows}
            if 1 not in avg or 0 not in avg:
                return None
            return float(avg[1] - avg[0])
        lt, ln = self._liked
        dt, dn = self._disliked
        if ln == 0 or dn == 0:
            return None
        return (lt / ln) - (dt / dn)

    @staticmethod
    def _db_ready() -> bool:
        from app.db import is_ready

        return is_ready()


outcome_store = OutcomeStore()
