"""사용 한도 — 체험(게스트)·로그인 회원·서비스 전체의 하루 몫.

돈이 나가거나(LLM·Google) 서버를 오래 붙잡는(코스 생성·합치기·검색) 기능만 센다.
수동 편집·조회처럼 싸고 가벼운 건 세지 않는다.

- **게스트(체험)**: 로그인 없이 한 번 써 보는 사람. 몫이 "평생 1회분"이다(하루가 지나도
  다시 차지 않는다). 다 쓰면 `login_required` — 로그인하면 회원 몫이 열린다.
- **회원**: 로그인한 무료 사용자. 몫이 하루 단위(한국 시각 자정에 다시 찬다).
- **IP**: 게스트 발급과 게스트 코스 생성은 IP 당 하루 상한을 따로 둔다 — 브라우저 저장소를
  지우고 새 게스트가 되는 걸 끝없이 반복하지 못하게.
- **서비스 전체**: 사람과 무관하게 하루 총량. 넘으면 비싼 기능은 폴백하거나 잠시 닫는다.
  사람 단위 제한을 전부 뚫려도 청구서가 이 선을 넘지 않게 하는 마지막 안전장치다.

카운터는 `api_quota` 테이블에 키 하나당 행 하나로 영속화한다(재시작으로 몫이 되살아나지 않게).
키가 날짜로 시작해 오래된 행은 사전순 비교 한 번으로 지운다(`prune`).
IP 는 원문 대신 서명 키로 해시해 저장한다.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone

from app.config import settings

logger = logging.getLogger("coursepilot")

KST = timezone(timedelta(hours=9))


@dataclass(frozen=True)
class Limit:
    guest: int  # 체험 전체 기간 몫
    member: int  # 하루 몫


# 기능별 사람 단위 한도. 게스트는 "한 번 써 보기"에 딱 맞게, 회원은 무료로 넉넉히.
LIMITS: dict[str, Limit] = {
    "course": Limit(guest=1, member=20),  # 새 코스(빈 코스 포함) 만들기
    "ai": Limit(guest=5, member=30),  # AI 코스 생성·수정·완화(LLM + 장소 검색 다수)
    "ask": Limit(guest=5, member=40),  # 코스를 바꾸지 않는 질문·되묻기(LLM 답변·해석을 부를 수 있다). 규칙 답변이 먼저라 실제 LLM 은 일부
    "build": Limit(guest=3, member=20),  # 두 사람 카드 합치기(장소 검색 6~24회)
    "review": Limit(guest=3, member=30),  # 리뷰 요약(Google 2콜 + LLM)
    "search": Limit(guest=30, member=300),  # 장소 직접 검색(카카오)
}

# 서비스 전체 하루 총량. 사람 수가 늘면 여기부터 올린다(청구서의 상한선).
GLOBAL_DAILY: dict[str, int] = {
    "guest": 300,  # 새 게스트 발급
    "course": 1_000,
    "ai": 1_500,
    "build": 500,
    "review": 300,
    "search": 10_000,
    "llm": 1_000,  # LLM 호출 전체(조건 분해·편집 해석·답변·요약). 넘으면 규칙 기반 폴백
    "google.details": 40,  # Place Details Enterprise — 콘솔 일일 할당량과 같게
    "google.map_id": 300,  # Text Search IDs-only — 콘솔 일일 할당량과 같게
    "google.reviews": 100,  # 리뷰 요약용 구형 Places(텍스트검색+상세) 호출
}


# 초대 보상: 같이 정하기 링크로 온 사람이 **새 회원**이 되면 두 사람 모두 7일 동안 회원 하루 몫에 더한다.
# 한 번에 주는 쿠폰(잔액 관리)이 아니라 "기간 동안 하루 몫 +N" 이라 기존 카운터를 그대로 쓴다.
# 보상을 다시 받으면 기간이 마지막 보상부터 7일로 늘어난다(겹쳐 쌓이지는 않는다).
# 체험(게스트) 몫에는 더하지 않는다 — 체험은 로그인으로 이어지는 입구다.
# 서비스 전체 상한(GLOBAL_DAILY)은 그대로다 — 청구서의 상한선은 보상으로도 뚫리지 않는다.
# 누가 보상을 받는지(새 회원만·1회·초대자 상한)는 app/referrals.py 가 정한다.
INVITE_BONUS: dict[str, int] = {"course": 5, "ai": 20, "build": 5}
INVITE_BONUS_DAYS = 7


class UsageDenied(Exception):
    """한도에 걸렸다. `code` 로 프론트가 다음 행동(체험 시작·로그인·내일)을 고른다."""

    def __init__(self, code: str, message: str, status: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def guest_required() -> UsageDenied:
    return UsageDenied(
        "guest_required", "시작하기를 먼저 눌러 주세요. 가입 없이 한 번 써 볼 수 있어요.", 401
    )


def login_required(what: str = "") -> UsageDenied:
    lead = f"{what} 체험 횟수를 다 썼어요." if what else "체험은 여기까지예요."
    return UsageDenied("login_required", f"{lead} 로그인하면 무료로 더 쓸 수 있어요.", 403)


def daily_limit() -> UsageDenied:
    return UsageDenied("daily_limit", "오늘 쓸 수 있는 횟수를 다 썼어요. 내일 다시 열려요.", 429)


def service_busy() -> UsageDenied:
    return UsageDenied(
        "service_busy", "오늘 준비한 분량이 다 찼어요. 내일 다시 이용해 주세요.", 503
    )


_FEATURE_NAMES = {
    "course": "코스 만들기",
    "ai": "AI 수정",
    "ask": "AI 질문",
    "build": "코스 합치기",
    "review": "리뷰 요약",
    "search": "장소 검색",
}


def today(now: datetime | None = None) -> str:
    return (now or datetime.now(KST)).astimezone(KST).strftime("%Y-%m-%d")


def ip_subject(ip: str) -> str:
    """IP 원문을 저장하지 않는다 — 서명 키로 해시한 앞 16자만."""
    key = (settings.session_secret or "dev").encode()
    return "ip-" + hmac.new(key, ip.encode(), hashlib.sha256).hexdigest()[:16]


class CounterStore:
    """키별 정수 카운터. DB 가 있으면 `api_quota` 행 잠금으로 원자적으로 늘린다."""

    def __init__(self) -> None:
        self._mem: dict[str, int] = {}

    def used(self, key: str) -> int:
        if _db_ready():
            from app.db import SessionLocal
            from app.models import QuotaModel

            with SessionLocal() as s:
                row = s.get(QuotaModel, key)
                return int(row.used) if row else 0
        return self._mem.get(key, 0)

    def take(self, key: str, limit: int) -> bool:
        """몫이 남았으면 1 늘리고 True. 없으면 그대로 False."""
        if limit <= 0:
            return False
        if _db_ready():
            return self._take_db(key, limit)
        used = self._mem.get(key, 0)
        if used >= limit:
            return False
        self._mem[key] = used + 1
        return True

    def give_back(self, key: str) -> None:
        """실패·되묻기처럼 결과를 못 준 요청의 몫을 돌려준다."""
        if _db_ready():
            from app.db import SessionLocal
            from app.models import QuotaModel

            with SessionLocal() as s:
                row = s.get(QuotaModel, key, with_for_update=True)
                if row is not None and row.used > 0:
                    row.used -= 1
                    s.commit()
            return
        if self._mem.get(key, 0) > 0:
            self._mem[key] -= 1

    def _take_db(self, key: str, limit: int) -> bool:
        from sqlalchemy.exc import IntegrityError

        from app.db import SessionLocal
        from app.models import QuotaModel

        for _ in range(2):  # 첫 행을 두 요청이 동시에 만들면 한쪽이 충돌한다 → 한 번 더
            with SessionLocal() as s:
                row = s.get(QuotaModel, key, with_for_update=True)
                if row is None:
                    s.add(QuotaModel(key=key, used=1))
                else:
                    if row.used >= limit:
                        return False
                    row.used += 1
                try:
                    s.commit()
                    return True
                except IntegrityError:
                    s.rollback()
        return False

    def delete_keys(self, keys: list[str]) -> int:
        if _db_ready():
            from sqlalchemy import delete

            from app.db import SessionLocal
            from app.models import QuotaModel

            with SessionLocal() as s:
                res = s.execute(delete(QuotaModel).where(QuotaModel.key.in_(keys)))
                s.commit()
                return int(res.rowcount or 0)
        gone = [k for k in keys if k in self._mem]
        for k in gone:
            del self._mem[k]
        return len(gone)

    def prune(self, keep_days: int = 14, now: datetime | None = None) -> int:
        """날짜로 시작하는 카운터 중 keep_days 보다 오래된 것을 지운다."""
        cutoff = today((now or datetime.now(KST)) - timedelta(days=keep_days))
        removed = 0
        for head in ("d:", "g:"):
            bound = f"{head}{cutoff}"
            if _db_ready():
                from sqlalchemy import and_, delete

                from app.db import SessionLocal
                from app.models import QuotaModel

                with SessionLocal() as s:
                    res = s.execute(
                        delete(QuotaModel).where(
                            and_(QuotaModel.key.startswith(head), QuotaModel.key < bound)
                        )
                    )
                    s.commit()
                    removed += int(res.rowcount or 0)
            else:
                gone = [k for k in self._mem if k.startswith(head) and k < bound]
                for k in gone:
                    del self._mem[k]
                removed += len(gone)
        return removed

    def clear(self) -> None:
        self._mem.clear()


counters = CounterStore()


def _db_ready() -> bool:
    try:
        from app.db import is_ready

        return is_ready()
    except Exception:  # pragma: no cover - 방어적
        return False


# ── 키 ────────────────────────────────────────────────────────────────────
def _person_key(feature: str, subject: str, guest: bool, now: datetime | None = None) -> str:
    # 게스트 몫은 날짜가 없다(평생 1회분). 회원·IP 몫은 날짜별 — 신원 없는 IP 는 통신사 NAT 뒤에
    # 여러 사람이 함께 있을 수 있어 평생 몫이면 영영 막힌다(하루 단위로 다시 찬다).
    if guest and not subject.startswith("ip-"):
        return f"t:{feature}:{subject}"
    return f"d:{today(now)}:{feature}:{subject}"


def _global_key(name: str, now: datetime | None = None) -> str:
    return f"g:{today(now)}:{name}"


# ── 서비스 전체 ───────────────────────────────────────────────────────────
RUNTIME_DETAILS_PER_DAY = 20  # 코스 확정 시 영업시간 갱신 몫(배치 몫과 별도)


def _global_limit(name: str) -> int | None:
    if name == "google.details" and settings.google_details_per_day > 20:
        # 배치 하루 몫을 기본(20)보다 올렸으면 하루 상한도 같이 오른다(콘솔 일일 할당량도 맞춰 올린다)
        return settings.google_details_per_day + RUNTIME_DETAILS_PER_DAY
    return GLOBAL_DAILY.get(name)


def global_take(name: str, now: datetime | None = None) -> bool:
    """서비스 전체 하루 몫에서 1 을 가져온다. 상한이 없는 이름은 항상 허용."""
    limit = _global_limit(name)
    if limit is None:
        return True
    ok = counters.take(_global_key(name, now), limit)
    if not ok:
        _warn_once(name, limit)
    return ok


def global_used(name: str, now: datetime | None = None) -> int:
    return counters.used(_global_key(name, now))


_warned: set[str] = set()


def _warn_once(name: str, limit: int) -> None:
    key = f"{today()}:{name}"
    if key in _warned:
        return
    _warned.add(key)
    text = f"서비스 하루 상한 도달: {name} ({limit}) — 오늘 남은 요청은 폴백하거나 막습니다"
    logger.warning(text)
    try:
        from app.alerting import alert_notifier

        alert_notifier.notify("usage", name, text)
    except Exception:  # pragma: no cover - 알림 실패가 요청을 막지 않게
        pass


# ── 사람 단위 ─────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Ticket:
    """한 번 가져간 몫. 결과를 못 줬으면 `release()` 로 돌려준다."""

    keys: tuple[str, ...]

    def release(self) -> None:
        for key in self.keys:
            counters.give_back(key)


def charge(
    feature: str,
    *,
    subject: str,
    guest: bool,
    ip: str | None = None,
    now: datetime | None = None,
) -> Ticket:
    """기능 1회를 쓴다. 한도에 걸리면 `UsageDenied`.

    순서: 사람 몫 → (게스트 코스면) IP 몫 → 서비스 전체 몫. 뒤에서 걸리면 앞에서 가져간 걸 돌려준다.
    """
    limit = LIMITS[feature]
    taken: list[str] = []

    from app.qa import learning_on

    if not learning_on():
        # 운영 자동 QA(토큰 확인됨): 사람·IP 몫은 건너뛴다 — 배포가 잦은 날 점검이 한도에 걸려 거짓 경보를
        # 내지 않게. 서비스 전체 상한은 그대로 센다(점검도 비용이다).
        gkey = _global_key(feature, now)
        glimit = GLOBAL_DAILY.get(feature)
        if glimit is not None:
            if not counters.take(gkey, glimit):
                raise service_busy()
            taken.append(gkey)
        return Ticket(tuple(taken))

    person = _person_key(feature, subject, guest, now)
    if not counters.take(person, limit.guest if guest else member_limit(feature, subject, now)):
        raise login_required(_FEATURE_NAMES.get(feature, "")) if guest else daily_limit()
    taken.append(person)

    if guest and feature == "course" and ip:
        ip_key = f"d:{today(now)}:course:{ip_subject(ip)}"
        if not counters.take(ip_key, settings.trial_courses_per_ip_day):
            Ticket(tuple(taken)).release()
            raise UsageDenied(
                "login_required",
                "이 네트워크에서는 오늘 체험 코스를 이미 만들었어요. 로그인하면 바로 더 만들 수 있어요.",
                403,
            )
        taken.append(ip_key)

    gkey = _global_key(feature, now)
    glimit = GLOBAL_DAILY.get(feature)
    if glimit is not None:
        if not counters.take(gkey, glimit):
            Ticket(tuple(taken)).release()
            _warn_once(feature, glimit)
            raise service_busy()
        taken.append(gkey)
    return Ticket(tuple(taken))


def allow_new_guest(ip: str, now: datetime | None = None) -> bool:
    """IP 당 하루 게스트 발급 상한 + 서비스 전체 게스트 발급 상한."""
    ip_key = f"d:{today(now)}:guest:{ip_subject(ip)}"
    if not counters.take(ip_key, settings.trial_guests_per_ip_day):
        return False
    if not global_take("guest", now):
        counters.give_back(ip_key)
        return False
    return True


def remaining(feature: str, *, subject: str, guest: bool, now: datetime | None = None) -> int:
    limit = LIMITS[feature]
    cap = limit.guest if guest else member_limit(feature, subject, now)
    return max(0, cap - counters.used(_person_key(feature, subject, guest, now)))


def invite_bonus_until(subject: str, now: datetime | None = None) -> datetime | None:
    """초대 보상이 켜져 있으면 끝나는 시각(UTC, tz 없음). 없거나 지났으면 None."""
    from app.referrals import referral_store

    last = referral_store.last_reward_at(subject)
    if last is None:
        return None
    until = last + timedelta(days=INVITE_BONUS_DAYS)
    ref = (now or datetime.now(UTC)).astimezone(UTC).replace(tzinfo=None)
    return until if ref < until else None


def member_limit(feature: str, subject: str, now: datetime | None = None) -> int:
    """회원 하루 몫 = 기본 + (초대 보상 기간이면) INVITE_BONUS."""
    base = LIMITS[feature].member
    extra = INVITE_BONUS.get(feature, 0)
    if extra and invite_bonus_until(subject, now) is not None:
        return base + extra
    return base


def forget_subject(subject: str) -> int:
    """게스트를 지울 때 그 사람의 체험 카운터도 지운다."""
    return counters.delete_keys([f"t:{f}:{subject}" for f in LIMITS])
