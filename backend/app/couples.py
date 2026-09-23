"""우리 기록 — 같은 커플이 매주 같은 곳을 받지 않게, 각자 좋았던 곳을 다음 코스에 반영.

평가 1차에서 확인된 문제: 한 상권 6코스 중 4개에 같은 가게(다양성 67%). 서로 다른 커플에겐 괜찮지만
같은 커플에겐 "항상 똑같은 코스"(데이트 불만 4위)다.

커플 = 시작한 사람(가입자 id) + 상대 이름. 가입 없이도 상대를 구분하려고 이름을 쓴다.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.db import is_ready


@dataclass
class CoupleState:
    visited: list[str] = field(default_factory=list)  # 다녀온 장소 id(최근 순)
    visited_names: dict[str, str] = field(default_factory=dict)  # id → 이름(화면용)
    ratings: dict[str, dict[str, int]] = field(default_factory=dict)  # 이름 → {장소 id: +1/-1}
    last_yielded: str | None = None  # 지난 코스에서 양보한 사람 → 다음엔 먼저
    courses: int = 0

    def disliked(self) -> set[str]:
        return {pid for r in self.ratings.values() for pid, v in r.items() if v < 0}

    def liked_by_both(self) -> set[str]:
        sets = [{pid for pid, v in r.items() if v > 0} for r in self.ratings.values()]
        return set.intersection(*sets) if len(sets) >= 2 else set()

    def exclude_ids(self) -> set[str]:
        """다음 코스에서 뺄 곳: 다녀온 곳(둘 다 👍 한 곳은 '또 가자'로 허용) + 누구라도 👎 한 곳."""
        return (set(self.visited) - self.liked_by_both()) | self.disliked()


def couple_key(owner_id: str | None, partner_name: str | None) -> str | None:
    if not owner_id or not partner_name:
        return None
    return f"{owner_id}:{partner_name.strip()}"


class CoupleStore:
    MAX_VISITED = 200

    def __init__(self) -> None:
        self._mem: dict[str, dict] = {}

    def get(self, key: str) -> CoupleState:
        raw = None
        if is_ready():
            from app.db import SessionLocal
            from app.models import CoupleModel

            with SessionLocal() as s:
                row = s.get(CoupleModel, key)
                raw = row.state if row else None
        else:
            raw = self._mem.get(key)
        return CoupleState(**raw) if raw else CoupleState()

    def save(self, key: str, st: CoupleState) -> None:
        st.visited = st.visited[: self.MAX_VISITED]
        data = asdict(st)
        if is_ready():
            from app.db import SessionLocal
            from app.models import CoupleModel

            with SessionLocal() as s:
                row = s.get(CoupleModel, key)
                if row:
                    row.state = data
                else:
                    s.add(CoupleModel(key=key, state=data))
                s.commit()
        else:
            self._mem[key] = data

    def record_visit(self, key: str, places: list[tuple[str, str]], yielded: str | None) -> CoupleState:
        st = self.get(key)
        for pid, name in places:
            if pid in st.visited:
                st.visited.remove(pid)
            st.visited.insert(0, pid)
            st.visited_names[pid] = name
        st.courses += 1
        if yielded:
            st.last_yielded = yielded
        self.save(key, st)
        return st

    def rate(self, key: str, who: str, ratings: dict[str, int]) -> CoupleState:
        st = self.get(key)
        mine = st.ratings.setdefault(who, {})
        for pid, v in ratings.items():
            if v in (1, -1):
                mine[pid] = v
            elif v == 0:
                mine.pop(pid, None)
        self.save(key, st)
        return st

    def reset(self) -> None:  # 테스트용
        self._mem.clear()


couple_store = CoupleStore()
