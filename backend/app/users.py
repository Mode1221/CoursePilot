"""회원/크레딧/온보딩 서비스 (9장).

- 과금 단위는 세션(코스)이 아닌 사용자 크레딧 소비로 트래킹하되, 사용자에게는 "질문 N회"로 노출.
- 수동 편집은 크레딧 미차감(무료), AI 챗봇 명령만 차감.
- 매월 리셋(이월 불가).
- DB 미사용 시 인메모리 폴백.
"""
from __future__ import annotations

import secrets
from datetime import date

from pydantic import BaseModel

from app.db import is_ready


MAX_REFERRAL_BONUS = 10  # 한 계정이 레퍼럴로 받을 수 있는 보너스 횟수 상한


class Preferences(BaseModel):
    """온보딩 선호 프로필 (모두 선택). AI 요청 컨텍스트에 자동 포함."""

    mood: str | None = None          # 조용한/활기찬
    budget: str | None = None        # 예산대
    region: str | None = None        # 자주 가는 지역
    diet: list[str] = []             # 비건/알러지
    transport: str | None = None     # 도보/차량


class User(BaseModel):
    id: str
    phone: str
    credits_limit: int = 5
    credits_used: int = 0
    credit_period: str = ""
    points: int = 0  # 구매 포인트(이월). 무료 크레딧 소진 후 사용
    referral_bonus_count: int = 0  # 레퍼럴로 받은 보너스 횟수(상한 확인용)
    preferences: Preferences = Preferences()

    @property
    def free_left(self) -> int:
        return max(0, self.credits_limit - self.credits_used)

    @property
    def credits_left(self) -> int:
        """사용자에게 노출되는 '질문 N회' = 무료 잔여 + 구매 포인트."""
        return self.free_left + self.points


class CreditError(Exception):
    """크레딧 소진."""


def _period_now() -> str:
    today = date.today()
    return f"{today.year:04d}-{today.month:02d}"


class UserStore:
    def __init__(self) -> None:
        self._mem: dict[str, User] = {}

    def create(self, phone: str, credits_limit: int = 5) -> User:
        user = User(
            id=secrets.token_urlsafe(8),
            phone=phone,
            credits_limit=credits_limit,
            credit_period=_period_now(),
        )
        return self._save(user)

    def grant_referral_bonus(self, user_id: str, amount: int) -> bool:
        """레퍼럴 보너스 지급. 상한(MAX_REFERRAL_BONUS)을 넘으면 지급하지 않는다.

        번호만 바꿔가며 자기 자신을 초대해 무한히 크레딧을 늘리는 것을 막는다.
        """
        user = self.get(user_id)
        if user is None or user.referral_bonus_count >= MAX_REFERRAL_BONUS:
            return False
        user.referral_bonus_count += 1
        user.credits_limit += amount
        self._save(user)
        return True

    def grant_credits(self, user_id: str, amount: int) -> User | None:
        """레퍼럴 등으로 무료 크레딧 추가 지급 (9-4). 한도 자체를 늘린다."""
        if is_ready():
            return self._add_locked(user_id, credits_limit=amount)
        user = self.get(user_id)
        if user is None:
            return None
        user.credits_limit += amount
        return self._save(user)

    def refund_credit(self, user_id: str) -> User | None:
        """소비한 크레딧 1회 되돌리기. 무료 사용분을 먼저 복원, 없으면 포인트로 환불."""
        if is_ready():
            return self._refund_credit_db(user_id)

        user = self.get(user_id)
        if user is None:
            return None
        if user.credits_used > 0:
            user.credits_used -= 1
        else:
            user.points += 1
        return self._save(user)

    def _refund_credit_db(self, user_id: str) -> User | None:
        """행 잠금으로 원자적 환불 → 동시 차감/환불에서 유실되지 않는다."""
        from app.db import SessionLocal
        from app.models import UserModel

        with SessionLocal() as s:
            row = s.get(UserModel, user_id, with_for_update=True)
            if row is None:
                return None
            if row.credits_used > 0:
                row.credits_used -= 1
            else:
                row.points += 1
            s.commit()
            return self._to_user(row)

    def find_by_phone(self, phone: str) -> User | None:
        """이미 가입한 번호인지 조회(재가입으로 무료 크레딧을 다시 받지 못하게)."""
        if is_ready():
            from sqlalchemy import select

            from app.db import SessionLocal
            from app.models import UserModel

            with SessionLocal() as s:
                row = s.execute(select(UserModel).where(UserModel.phone == phone)).scalar_one_or_none()
                return self._to_user(row) if row is not None else None
        return next((u for u in self._mem.values() if u.phone == phone), None)

    def get(self, user_id: str) -> User | None:
        if is_ready():
            from app.db import SessionLocal
            from app.models import UserModel

            with SessionLocal() as s:
                row = s.get(UserModel, user_id)
                if row is None:
                    return None
                return self._to_user(row)
        return self._mem.get(user_id)

    def preference_stats(self, limit: int = 5000) -> dict:
        """온보딩 설문 응답 집계(개인정보 없이 문항별 분포).

        설문을 실제로 채우는 비율을 봐야 문항 수·문구를 조정할 수 있다.
        """
        if is_ready():
            from sqlalchemy import select

            from app.db import SessionLocal
            from app.models import UserModel

            with SessionLocal() as s:
                rows = s.execute(select(UserModel.preferences).limit(limit)).all()
            prefs = [Preferences.model_validate(r[0] or {}) for r in rows]
        else:
            prefs = [u.preferences for u in list(self._mem.values())[:limit]]

        total = len(prefs)
        filled = {"mood": 0, "region": 0, "transport": 0, "budget": 0, "diet": 0}
        budgets: dict[str, int] = {}
        moods: dict[str, int] = {}
        diets: dict[str, int] = {}
        for pref in prefs:
            for field in ("mood", "region", "transport", "budget"):
                if getattr(pref, field):
                    filled[field] += 1
            if pref.diet:
                filled["diet"] += 1
            if pref.budget:
                budgets[pref.budget] = budgets.get(pref.budget, 0) + 1
            if pref.mood:
                moods[pref.mood] = moods.get(pref.mood, 0) + 1
            for d in pref.diet:
                diets[d] = diets.get(d, 0) + 1
        any_filled = sum(1 for p in prefs if p.mood or p.region or p.transport or p.budget or p.diet)
        return {
            "users": total,
            "answered_any": any_filled,
            "answered_rate": round(any_filled / total, 4) if total else None,
            "filled_by_question": filled,
            "budget_distribution": budgets,
            "mood_distribution": moods,
            "diet_distribution": diets,
        }

    def set_preferences(self, user_id: str, prefs: Preferences) -> User | None:
        if is_ready():
            # 전체 저장(_save)은 그 사이 바뀐 크레딧까지 되돌릴 수 있다 → 선호만 갱신
            from app.db import SessionLocal
            from app.models import UserModel

            with SessionLocal() as s:
                row = s.get(UserModel, user_id, with_for_update=True)
                if row is None:
                    return None
                row.preferences = prefs.model_dump()
                s.commit()
                return self._to_user(row)
        user = self.get(user_id)
        if user is None:
            return None
        user.preferences = prefs
        return self._save(user)

    def consume_credit(self, user_id: str) -> User:
        """AI 명령 1회 = 질문 1회 차감. 월 리셋 반영. 소진 시 CreditError."""
        if is_ready():
            return self._consume_credit_db(user_id)

        user = self.get(user_id)
        if user is None:
            raise CreditError("user not found")
        period = _period_now()
        if user.credit_period != period:  # 무료 크레딧만 매월 리셋(포인트는 이월)
            user.credit_period = period
            user.credits_used = 0
        if user.free_left > 0:
            user.credits_used += 1  # 무료 크레딧 우선 소비
        elif user.points > 0:
            user.points -= 1  # 무료 소진 시 구매 포인트 사용
        else:
            raise CreditError("no credits left")
        return self._save(user)

    def purchase_points(self, user_id: str, amount: int) -> User | None:
        """포인트 구매/충전 (9-2). 결제 성공 후 호출 가정. 이월된다."""
        if is_ready():
            return self._add_locked(user_id, points=amount)
        user = self.get(user_id)
        if user is None:
            return None
        user.points += amount
        return self._save(user)

    def _add_locked(self, user_id: str, *, points: int = 0, credits_limit: int = 0) -> User | None:
        """행 잠금으로 가산 → 동시 충전/지급이 유실되지 않는다."""
        from app.db import SessionLocal
        from app.models import UserModel

        with SessionLocal() as s:
            row = s.get(UserModel, user_id, with_for_update=True)
            if row is None:
                return None
            row.points += points
            row.credits_limit += credits_limit
            s.commit()
            return self._to_user(row)

    def _consume_credit_db(self, user_id: str) -> User:
        """행 잠금으로 원자적 차감 → 동시 요청의 초과 사용 방지."""
        from app.db import SessionLocal
        from app.models import UserModel

        period = _period_now()
        with SessionLocal() as s:
            row = s.get(UserModel, user_id, with_for_update=True)
            if row is None:
                raise CreditError("user not found")
            if row.credit_period != period:  # 무료 크레딧만 매월 리셋
                row.credit_period = period
                row.credits_used = 0
            if row.credits_limit - row.credits_used > 0:
                row.credits_used += 1  # 무료 우선
            elif row.points > 0:
                row.points -= 1  # 포인트 사용
            else:
                raise CreditError("no credits left")
            s.commit()
            return self._to_user(row)

    def _save(self, user: User) -> User:
        if is_ready():
            from app.db import SessionLocal
            from app.models import UserModel

            with SessionLocal() as s:
                row = s.get(UserModel, user.id)
                if row is None:
                    row = UserModel(id=user.id, phone=user.phone)
                    s.add(row)
                row.phone = user.phone
                row.credits_limit = user.credits_limit
                row.credits_used = user.credits_used
                row.credit_period = user.credit_period
                row.points = user.points
                row.referral_bonus_count = user.referral_bonus_count
                row.preferences = user.preferences.model_dump()
                s.commit()
            return user
        self._mem[user.id] = user
        return user

    @staticmethod
    def _to_user(row) -> User:
        return User(
            id=row.id,
            phone=row.phone,
            credits_limit=row.credits_limit,
            credits_used=row.credits_used,
            credit_period=row.credit_period,
            points=row.points,
            referral_bonus_count=getattr(row, "referral_bonus_count", 0) or 0,
            preferences=Preferences.model_validate(row.preferences or {}),
        )


user_store = UserStore()
