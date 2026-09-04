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
    preferences: Preferences = Preferences()

    @property
    def credits_left(self) -> int:
        return max(0, self.credits_limit - self.credits_used)


class CreditError(Exception):
    """크레딧 소진."""


def _period_now() -> str:
    today = date.today()
    return f"{today.year:04d}-{today.month:02d}"


class UserStore:
    def __init__(self) -> None:
        self._mem: dict[str, User] = {}
        self._db_ready = False

    def enable_db(self, ready: bool) -> None:
        self._db_ready = ready

    def create(self, phone: str, credits_limit: int = 5) -> User:
        user = User(
            id=secrets.token_urlsafe(8),
            phone=phone,
            credits_limit=credits_limit,
            credit_period=_period_now(),
        )
        return self._save(user)

    def grant_credits(self, user_id: str, amount: int) -> User | None:
        """레퍼럴 등으로 무료 크레딧 추가 지급 (9-4)."""
        user = self.get(user_id)
        if user is None:
            return None
        user.credits_limit += amount
        return self._save(user)

    def get(self, user_id: str) -> User | None:
        if self._db_ready:
            from app.db import SessionLocal
            from app.models import UserModel

            with SessionLocal() as s:
                row = s.get(UserModel, user_id)
                if row is None:
                    return None
                return self._to_user(row)
        return self._mem.get(user_id)

    def set_preferences(self, user_id: str, prefs: Preferences) -> User | None:
        user = self.get(user_id)
        if user is None:
            return None
        user.preferences = prefs
        return self._save(user)

    def consume_credit(self, user_id: str) -> User:
        """AI 명령 1회 = 질문 1회 차감. 월 리셋 반영. 소진 시 CreditError."""
        user = self.get(user_id)
        if user is None:
            raise CreditError("user not found")
        period = _period_now()
        if user.credit_period != period:  # 매월 리셋(이월 불가)
            user.credit_period = period
            user.credits_used = 0
        if user.credits_left <= 0:
            raise CreditError("no credits left")
        user.credits_used += 1
        return self._save(user)

    def _save(self, user: User) -> User:
        if self._db_ready:
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
            preferences=Preferences.model_validate(row.preferences or {}),
        )


user_store = UserStore()
