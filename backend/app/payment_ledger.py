"""결제 사용 이력(중복 지급 방지).

같은 imp_uid 로 여러 번 충전 요청이 오면 두 번째부터는 거절한다.
DB 가 있으면 payments 테이블에 남겨 재시작·다중 인스턴스에서도 유지되고,
없으면 개발용 인메모리로 폴백한다.
"""
from __future__ import annotations

from collections import OrderedDict

from app.db import is_ready

MAX_ENTRIES = 5000  # 인메모리 폴백에서만: 오래된 것부터 버린다(무한 증가 방지)


class PaymentLedger:
    def __init__(self) -> None:
        self._used: OrderedDict[str, None] = OrderedDict()

    def is_used(self, imp_uid: str) -> bool:
        if is_ready():
            from app.db import SessionLocal
            from app.models import PaymentModel

            with SessionLocal() as s:
                return s.get(PaymentModel, imp_uid) is not None
        return imp_uid in self._used

    def mark_used(self, imp_uid: str, user_id: str = "", points: int = 0) -> None:
        if is_ready():
            from sqlalchemy.exc import IntegrityError

            from app.db import SessionLocal
            from app.models import PaymentModel

            with SessionLocal() as s:
                s.add(PaymentModel(imp_uid=imp_uid, user_id=user_id, points=points))
                try:
                    s.commit()
                except IntegrityError:  # 동시 요청이 먼저 기록 → 이미 처리된 결제
                    s.rollback()
            return
        self._used[imp_uid] = None
        self._used.move_to_end(imp_uid)
        while len(self._used) > MAX_ENTRIES:
            self._used.popitem(last=False)

    def clear(self) -> None:
        self._used.clear()


payment_ledger = PaymentLedger()
