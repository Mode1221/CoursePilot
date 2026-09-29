"""재방문 의사("또 가고 싶어요") 중복 방지.

명시 신호는 한 사람이 한 장소에 한 번만 의미가 있다. 반복 호출로 인기 점수를
부풀리지 못하게 (사용자, 장소) 쌍을 기억한다. DB 없이도 동작하도록 인메모리이며,
장기 구동에서 계속 늘지 않게 상한을 둔다.
"""
from __future__ import annotations

MAX_ENTRIES = 100_000


class RevisitStore:
    def __init__(self) -> None:
        self._mem: set[tuple[str, str]] = set()

    def mark(self, user_id: str, place_id: str) -> bool:
        """처음이면 True(신호 반영), 이미 표시했으면 False."""
        key = (user_id, place_id)
        if key in self._mem:
            return False
        if len(self._mem) >= MAX_ENTRIES:
            self._mem.pop()  # 오래된 것을 특정할 수 없으므로 임의 축출
        self._mem.add(key)
        return True

    def clear(self) -> None:
        self._mem.clear()


revisit_store = RevisitStore()
