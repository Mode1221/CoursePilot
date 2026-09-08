"""결제 사용 이력(중복 지급 방지).

같은 imp_uid 로 여러 번 충전 요청이 오면 두 번째부터는 거절한다.
단일 프로세스 인메모리이므로, 다중 인스턴스·재시작 내구성이 필요하면
DB 테이블(결제 원장)로 옮겨야 한다.
"""
from __future__ import annotations

from collections import OrderedDict

MAX_ENTRIES = 5000  # 오래된 것부터 버린다(무한 증가 방지)


class PaymentLedger:
    def __init__(self) -> None:
        self._used: OrderedDict[str, None] = OrderedDict()

    def is_used(self, imp_uid: str) -> bool:
        return imp_uid in self._used

    def mark_used(self, imp_uid: str) -> None:
        self._used[imp_uid] = None
        self._used.move_to_end(imp_uid)
        while len(self._used) > MAX_ENTRIES:
            self._used.popitem(last=False)

    def clear(self) -> None:
        self._used.clear()


payment_ledger = PaymentLedger()
