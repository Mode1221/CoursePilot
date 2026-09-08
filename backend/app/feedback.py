"""피드백 이벤트 로깅 (data #15/#16).

조건 완화 제안·수락·거부 등 사용자 반응을 기록해 "어떤 제약이 진짜 하드인지"를
학습할 데이터로 축적한다. DB/인메모리 폴백.

kind 예시:
  relax_offered   — 완화 제안(needs_confirmation)
  relax_accepted  — 사용자가 완화 결과 수락
  relax_rejected  — 사용자가 조건을 직접 바꿈(완화 거부)
"""
from __future__ import annotations

from collections import defaultdict


class FeedbackStore:
    def __init__(self) -> None:
        # 집계(kind별 카운트)만 쓰이므로 이벤트 원문을 쌓지 않는다(무한 증가 방지)
        self._mem: dict[str, int] = defaultdict(int)

    def log(self, course_id: str, kind: str, detail: str = "") -> None:
        if self._db_ready():
            from app.db import SessionLocal
            from app.models import FeedbackModel

            with SessionLocal() as s:
                s.add(FeedbackModel(course_id=course_id, kind=kind, detail=detail))
                s.commit()
            return
        self._mem[kind] += 1

    def counts(self, kind: str | None = None) -> dict[str, int]:
        """kind별 집계(간단 학습용). DB/인메모리 공통."""
        if self._db_ready():
            from sqlalchemy import func, select

            from app.db import SessionLocal
            from app.models import FeedbackModel

            with SessionLocal() as s:
                stmt = select(FeedbackModel.kind, func.count()).group_by(FeedbackModel.kind)
                if kind:
                    stmt = stmt.where(FeedbackModel.kind == kind)
                return {k: n for k, n in s.execute(stmt).all()}
        if kind is not None:
            return {kind: self._mem[kind]} if self._mem.get(kind) else {}
        return dict(self._mem)

    def acceptance_rate(self, default: float = 0.5) -> float:
        """완화 수용률(#16). accepted/(accepted+rejected). 표본 없으면 default.

        높을수록 사용자가 완화를 잘 받아들인다 → 완화를 더 과감히 적용.
        """
        c = self.counts()
        acc = c.get("relax_accepted", 0)
        rej = c.get("relax_rejected", 0)
        total = acc + rej
        return acc / total if total else default

    @staticmethod
    def _db_ready() -> bool:
        from app.db import is_ready

        return is_ready()


feedback_store = FeedbackStore()
