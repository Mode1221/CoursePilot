"""계정·인증·결제 엔드포인트.

가입/인증번호, 선호 프로필, 크레딧과 포인트 구매처럼 "사람"에 관한 라우팅을
한곳에 모은다. 코스 관련 라우팅(main)과 섞이면 어느 쪽을 고치는지 흐려진다.
"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from app.config import settings
from app.middleware import client_ip
from app.session_token import issue
from app.users import Preferences, user_store

accounts_router = APIRouter(tags=["accounts"])


class _PhoneBody(BaseModel):
    """전화번호를 받는 요청의 공통 규칙. 표기가 달라도 같은 번호로 다룬다."""

    phone: str = Field(min_length=9, max_length=20, pattern=r"^[0-9\-+ ]+$")

    @field_validator("phone")
    @classmethod
    def _normalize(cls, v: str) -> str:
        from app.auth import normalize_phone

        return normalize_phone(v)


class SignupRequest(_PhoneBody):
    # 전화번호 인증은 별도 프로세스 가정, 여기선 인증 완료 후 호출
    referrer_id: str | None = Field(default=None, max_length=64)  # 9-4 레퍼럴


REFERRAL_BONUS = 1


class SmsRequestBody(_PhoneBody):
    pass


class SmsVerifyBody(_PhoneBody):
    code: str = Field(min_length=6, max_length=6, pattern=r"^[0-9]{6}$")


@accounts_router.post("/auth/sms/request")
async def sms_request(req: SmsRequestBody, request: Request) -> dict:
    """인증번호 발송. 개발(키 미설정)에서만 코드를 응답에 노출한다.

    운영에서 SMS 키가 없으면 코드를 그대로 돌려주게 되는데, 그건 누구나
    남의 번호로 가입할 수 있다는 뜻이다. 노출 대신 거절한다.
    """
    from app.auth import SmsSendFailed, TooManyRequests, request_code

    if settings.is_production and not settings.sms_enabled and not settings.sms_dev_fallback:
        raise HTTPException(
            status_code=503,
            detail="문자 인증을 사용할 수 없습니다. 잠시 후 다시 시도해주세요.",
        )

    try:
        dev_code = await request_code(req.phone, client_ip(request))
    except TooManyRequests:
        raise HTTPException(
            status_code=429, detail="잠시 후 다시 요청해주세요."
        ) from None
    except SmsSendFailed:
        raise HTTPException(
            status_code=502, detail="인증번호를 보내지 못했어요. 잠시 후 다시 시도해주세요."
        ) from None
    return {"sent": True, "dev_code": dev_code}  # dev_code 는 SMS 활성 시 null


@accounts_router.post("/auth/sms/verify")
async def sms_verify(
    req: SmsVerifyBody,
    x_user_id: str | None = Header(default=None),
    x_user_token: str | None = Header(default=None),
) -> dict:
    from app.auth import can_resume_existing, verification_store

    ok = verification_store.verify(req.phone, req.code)
    if not ok:
        raise HTTPException(status_code=400, detail="인증번호가 올바르지 않거나 만료되었습니다")
    # 이미 가입한 번호면 토큰을 새로 끊어 준다 — 만료(90일)로 돌아온 사용자가
    # 인증만 다시 하면 바로 쓰던 계정으로 이어지게 한다(진짜 SMS 일 때만).
    existing = user_store.find_by_phone(req.phone)
    if existing is not None and can_resume_existing():
        return _logged_in(existing.id, _guest_of(x_user_id, x_user_token))
    return {"verified": True}


@accounts_router.post("/signup")
async def signup(
    req: SignupRequest,
    x_user_id: str | None = Header(default=None),
    x_user_token: str | None = Header(default=None),
) -> dict:
    from app.auth import can_resume_existing, require_verified, verification_store

    if not require_verified(req.phone):
        raise HTTPException(status_code=403, detail="전화번호 인증이 필요합니다")
    verification_store.consume_verified(req.phone)  # 1회성 소비
    guest_id = _guest_of(x_user_id, x_user_token)
    existing = user_store.find_by_phone(req.phone)
    if existing is not None:
        if not can_resume_existing():
            # 인증번호가 화면에 보이는 폴백으로는 남의 기존 계정에 들어갈 수 없다
            raise HTTPException(status_code=409, detail="이미 가입된 번호예요. 다른 방법으로 로그인해 주세요.")
        # 이미 가입한 번호면 그 계정으로 다시 들어온다(재가입 크레딧 어뷰징 차단)
        return _logged_in(existing.id, guest_id)
    user = user_store.create(req.phone)
    # 신규 가입 시 초대자에게 보너스 크레딧. 자기추천 방지 + 실존 초대자만.
    if (
        req.referrer_id
        and req.referrer_id != user.id
        and user_store.get(req.referrer_id) is not None
    ):
        user_store.grant_referral_bonus(req.referrer_id, REFERRAL_BONUS)
    return _logged_in(user.id, guest_id)


def _guest_of(user_id: str | None, token: str | None) -> str | None:
    """로그인 요청에 함께 온 체험 계정 id(서명이 맞을 때만). 없거나 회원이면 None."""
    from app.identity import resolve_caller

    try:
        caller = resolve_caller(user_id, token)
    except HTTPException:
        return None
    return caller.user_id if caller and caller.guest else None


def _logged_in(user_id: str, guest_id: str | None) -> dict:
    """로그인 성공 응답. 체험 계정이 있었으면 그 코스·기록을 이 계정으로 옮긴다."""
    from app.identity import merge_guest

    moved = merge_guest(guest_id, user_id) if guest_id else 0
    user = user_store.get(user_id)
    return {
        "verified": True,
        "user_id": user_id,
        "token": issue(user_id),
        "kind": "member",
        "credits_left": user.credits_left if user else 0,
        "moved_courses": moved,
    }


class GuestRequest(BaseModel):
    nickname: str | None = Field(default=None, max_length=20)
    # 체험도 약관·개인정보처리방침·AI 처리 고지·만 14세 이상 동의가 있어야 시작한다
    agreed: bool


@accounts_router.post("/auth/guest")
async def start_guest(req: GuestRequest, request: Request) -> dict:
    """로그인 없이 한 번 써 보기. 서버가 체험 계정을 만들고 서명 토큰을 준다."""
    from app.identity import create_guest
    from app.usage import allow_new_guest

    if not req.agreed:
        raise HTTPException(status_code=400, detail="약관과 개인정보처리방침에 동의해 주세요")
    if not allow_new_guest(client_ip(request)):
        raise HTTPException(
            status_code=429,
            detail="오늘은 이 네트워크에서 체험을 더 시작할 수 없어요. 로그인하면 바로 쓸 수 있어요.",
        )
    nickname = (req.nickname or "").strip() or None
    user = create_guest(nickname)
    return {"user_id": user.id, "token": issue(user.id), "kind": "guest"}


@accounts_router.get("/me")
async def me(
    x_user_id: str | None = Header(default=None),
    x_user_token: str | None = Header(default=None),
) -> dict:
    """지금 신원과 남은 횟수. 체험 중이면 무엇이 몇 번 남았는지 보여 주려고."""
    from app.identity import resolve_caller
    from app.usage import LIMITS, remaining

    caller = resolve_caller(x_user_id, x_user_token)
    if caller is None:
        return {"kind": None}
    user = user_store.get(caller.user_id)
    left = {f: remaining(f, subject=caller.user_id, guest=caller.guest) for f in LIMITS}
    return {
        "kind": caller.kind,
        "user_id": caller.user_id,
        "nickname": user.preferences.nickname if user else None,
        "remaining": left,
        "limits": {f: (lim.guest if caller.guest else lim.member) for f, lim in LIMITS.items()},
    }


class KakaoLoginRequest(BaseModel):
    code: str = Field(min_length=1, max_length=512)
    redirect_uri: str = Field(min_length=1, max_length=300)


KAKAO_CALLBACK_PATH = "/auth/kakao"


def _allowed_redirect(uri: str) -> bool:
    """돌아올 주소는 우리 사이트의 콜백 경로뿐. 카카오 콘솔에도 같은 주소만 등록한다."""
    from urllib.parse import urlsplit

    parts = urlsplit(uri)
    origin = f"{parts.scheme}://{parts.netloc}"
    return parts.path == KAKAO_CALLBACK_PATH and origin in settings.cors_origins and not parts.query


@accounts_router.post("/auth/kakao")
async def kakao_login(
    req: KakaoLoginRequest,
    x_user_id: str | None = Header(default=None),
    x_user_token: str | None = Header(default=None),
) -> dict:
    """카카오 인가 코드로 로그인. 처음이면 계정을 만들고, 체험 중이었으면 그 기록을 옮긴다."""
    from app.adapters import kakao_auth
    from app.identity import KAKAO_PREFIX

    if not kakao_auth.enabled():
        raise HTTPException(status_code=503, detail="카카오 로그인을 아직 쓸 수 없어요")
    if not _allowed_redirect(req.redirect_uri):
        raise HTTPException(status_code=400, detail="잘못된 로그인 주소예요")
    try:
        kid = await kakao_auth.kakao_user_id(req.code, req.redirect_uri)
    except kakao_auth.KakaoLoginError:
        raise HTTPException(
            status_code=400, detail="카카오 로그인에 실패했어요. 다시 시도해 주세요."
        ) from None
    identity = f"{KAKAO_PREFIX}{kid}"
    user = user_store.find_by_phone(identity) or user_store.create(identity)
    return _logged_in(user.id, _guest_of(x_user_id, x_user_token))


def _require_self(
    user_id: str, x_user_id: str | None, x_user_token: str | None = None
) -> None:
    """개인 데이터는 본인 요청만 허용(id 를 안다고 남의 것을 볼 수 없게).

    id 는 공유 링크 등으로 새어 나갈 수 있는 값이라, 비밀키가 설정된 환경에서는
    서명 토큰까지 맞아야 통과시킨다.
    """
    from app.session_token import verify

    if x_user_id != user_id:
        raise HTTPException(status_code=403, detail="본인만 접근할 수 있어요")
    if not verify(user_id, x_user_token):
        raise HTTPException(status_code=401, detail="다시 로그인해 주세요")


@accounts_router.put("/users/{user_id}/preferences")
async def set_preferences(
    user_id: str, prefs: Preferences, x_user_id: str | None = Header(default=None),
    x_user_token: str | None = Header(default=None)) -> dict:
    _require_self(user_id, x_user_id, x_user_token)
    user = user_store.set_preferences(user_id, prefs)
    if user is None:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없어요")
    return {"ok": True}


@accounts_router.get("/users/{user_id}/preferences", response_model=Preferences)
async def get_preferences(
    user_id: str, x_user_id: str | None = Header(default=None),
    x_user_token: str | None = Header(default=None)) -> Preferences:
    """저장된 선호 프로필. 선호 설정 화면을 다시 열 때 기존 값을 보여주기 위함 —
    조회 수단이 없어 빈 폼으로 저장하면 기존 값이 통째로 지워졌다."""
    _require_self(user_id, x_user_id, x_user_token)
    user = user_store.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없어요")
    return user.preferences


@accounts_router.get("/users/{user_id}/credits")
async def get_credits(user_id: str, x_user_id: str | None = Header(default=None),
    x_user_token: str | None = Header(default=None)) -> dict:
    _require_self(user_id, x_user_id, x_user_token)
    user = user_store.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없어요")
    # 사용자에겐 "질문 N회 남음"으로만 노출 (토큰 비노출, 9-5)
    # free_mode 면 프론트가 잔여 횟수·구매 버튼을 숨긴다.
    return {"questions_left": user.credits_left, "free_mode": settings.free_mode}


class PurchaseRequest(BaseModel):
    # 구매할 포인트(질문 횟수). imp_uid 있으면 포트원으로 실제 결제 검증.
    points: int = Field(gt=0, le=1000)
    imp_uid: str | None = Field(default=None, max_length=64)


@accounts_router.post("/users/{user_id}/purchase")
async def purchase_points(
    user_id: str, req: PurchaseRequest, x_user_id: str | None = Header(default=None),
    x_user_token: str | None = Header(default=None)) -> dict:
    """포인트 구매/충전 (9-2). 결제 활성 시 imp_uid 로 결제 검증 후 지급.

    운영에서 결제 키가 없으면 검증 없이 포인트를 찍어 주게 된다 — 누구나 공짜로
    충전할 수 있다는 뜻이다. SMS 와 같은 이유로 지급 대신 거절한다.
    """
    if settings.is_production and not settings.payment_enabled:
        raise HTTPException(
            status_code=503,
            detail="결제를 사용할 수 없습니다. 잠시 후 다시 시도해주세요.",
        )
    _require_self(user_id, x_user_id, x_user_token)
    if req.points <= 0:
        raise HTTPException(status_code=400, detail="포인트는 1 이상이어야 합니다")
    if user_store.get(user_id) is None:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없어요")

    from app.adapters.payment import get_payment_service
    from app.payment_ledger import payment_ledger

    pay = get_payment_service()
    if pay is not None:
        # 실 결제 검증: 결제 완료 + 금액이 (포인트 수 × 단가) 이상이어야 지급
        if not req.imp_uid:
            raise HTTPException(status_code=400, detail="결제 정보(imp_uid)가 필요합니다")
        if payment_ledger.is_used(req.imp_uid):
            # 같은 결제로 반복 충전(리플레이) 차단
            raise HTTPException(status_code=409, detail="이미 처리된 결제입니다")
        from app.metrics import metrics_store

        try:
            result = await pay.verify(req.imp_uid)
            metrics_store.record_external("payment.verify", ok=True)
        except Exception:
            metrics_store.record_external("payment.verify", ok=False)
            raise HTTPException(status_code=502, detail="결제 검증에 실패했습니다") from None
        expected = req.points * settings.point_price_krw
        if not result.paid or result.amount < expected:
            raise HTTPException(status_code=402, detail="결제가 확인되지 않았습니다")
        # 기록에 실패했다면(동시 요청이 먼저 선점) 지급하지 않는다
        if not payment_ledger.mark_used(req.imp_uid, user_id=user_id, points=req.points):
            raise HTTPException(status_code=409, detail="이미 처리된 결제입니다")
    elif req.imp_uid:
        # 결제 키가 없어도(개발/키 누락 배포) 같은 결제 식별자의 반복 충전은 막는다.
        # 금액 검증은 결제사 조회가 필요하므로 이 경로에서는 생략한다.
        if not payment_ledger.mark_used(req.imp_uid, user_id=user_id, points=req.points):
            raise HTTPException(status_code=409, detail="이미 처리된 결제입니다")

    user = user_store.purchase_points(user_id, req.points)
    if user is None:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없어요")
    return {"questions_left": user.credits_left}
