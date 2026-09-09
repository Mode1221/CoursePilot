"""계정·인증·결제 엔드포인트.

가입/인증번호, 선호 프로필, 크레딧과 포인트 구매처럼 "사람"에 관한 라우팅을
한곳에 모은다. 코스 관련 라우팅(main)과 섞이면 어느 쪽을 고치는지 흐려진다.
"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.users import Preferences, user_store

accounts_router = APIRouter(tags=["accounts"])


class SignupRequest(BaseModel):
    # 전화번호 인증은 별도 프로세스 가정, 여기선 인증 완료 후 호출
    phone: str = Field(min_length=9, max_length=20, pattern=r"^[0-9\-+ ]+$")
    referrer_id: str | None = Field(default=None, max_length=64)  # 9-4 레퍼럴


REFERRAL_BONUS = 1


class SmsRequestBody(BaseModel):
    phone: str = Field(min_length=9, max_length=20, pattern=r"^[0-9\-+ ]+$")


class SmsVerifyBody(BaseModel):
    phone: str = Field(min_length=9, max_length=20, pattern=r"^[0-9\-+ ]+$")
    code: str = Field(min_length=6, max_length=6, pattern=r"^[0-9]{6}$")


@accounts_router.post("/auth/sms/request")
async def sms_request(req: SmsRequestBody) -> dict:
    """인증번호 발송. 실서비스는 발송만, 개발(키 미설정)은 코드를 응답에 노출."""
    from app.auth import SmsSendFailed, TooManyRequests, request_code

    try:
        dev_code = await request_code(req.phone)
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
async def sms_verify(req: SmsVerifyBody) -> dict:
    from app.auth import verification_store

    ok = verification_store.verify(req.phone, req.code)
    if not ok:
        raise HTTPException(status_code=400, detail="인증번호가 올바르지 않거나 만료되었습니다")
    return {"verified": True}


@accounts_router.post("/signup")
async def signup(req: SignupRequest) -> dict:
    from app.auth import require_verified, verification_store

    if not require_verified(req.phone):
        raise HTTPException(status_code=403, detail="전화번호 인증이 필요합니다")
    verification_store.consume_verified(req.phone)  # 1회성 소비
    existing = user_store.find_by_phone(req.phone)
    if existing is not None:
        # 이미 가입한 번호면 그 계정으로 다시 들어온다(재가입 크레딧 어뷰징 차단)
        return {"user_id": existing.id, "credits_left": existing.credits_left}
    user = user_store.create(req.phone)
    # 신규 가입 시 초대자에게 보너스 크레딧. 자기추천 방지 + 실존 초대자만.
    if (
        req.referrer_id
        and req.referrer_id != user.id
        and user_store.get(req.referrer_id) is not None
    ):
        user_store.grant_referral_bonus(req.referrer_id, REFERRAL_BONUS)
    return {"user_id": user.id, "credits_left": user.credits_left}


def _require_self(user_id: str, x_user_id: str | None) -> None:
    """개인 데이터는 본인 요청만 허용(id 를 안다고 남의 것을 볼 수 없게)."""
    if x_user_id != user_id:
        raise HTTPException(status_code=403, detail="본인만 접근할 수 있어요")


@accounts_router.put("/users/{user_id}/preferences")
async def set_preferences(
    user_id: str, prefs: Preferences, x_user_id: str | None = Header(default=None)
) -> dict:
    _require_self(user_id, x_user_id)
    user = user_store.set_preferences(user_id, prefs)
    if user is None:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없어요")
    return {"ok": True}


@accounts_router.get("/users/{user_id}/preferences", response_model=Preferences)
async def get_preferences(
    user_id: str, x_user_id: str | None = Header(default=None)
) -> Preferences:
    """저장된 선호 프로필. 선호 설정 화면을 다시 열 때 기존 값을 보여주기 위함 —
    조회 수단이 없어 빈 폼으로 저장하면 기존 값이 통째로 지워졌다."""
    _require_self(user_id, x_user_id)
    user = user_store.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없어요")
    return user.preferences


@accounts_router.get("/users/{user_id}/credits")
async def get_credits(user_id: str, x_user_id: str | None = Header(default=None)) -> dict:
    _require_self(user_id, x_user_id)
    user = user_store.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없어요")
    # 사용자에겐 "질문 N회 남음"으로만 노출 (토큰 비노출, 9-5)
    return {"questions_left": user.credits_left}


class PurchaseRequest(BaseModel):
    # 구매할 포인트(질문 횟수). imp_uid 있으면 포트원으로 실제 결제 검증.
    points: int = Field(gt=0, le=1000)
    imp_uid: str | None = Field(default=None, max_length=64)


@accounts_router.post("/users/{user_id}/purchase")
async def purchase_points(
    user_id: str, req: PurchaseRequest, x_user_id: str | None = Header(default=None)
) -> dict:
    """포인트 구매/충전 (9-2). 결제 활성 시 imp_uid 로 결제 검증 후 지급."""
    _require_self(user_id, x_user_id)
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
        payment_ledger.mark_used(req.imp_uid, user_id=user_id, points=req.points)
    elif req.imp_uid:
        # 결제 키가 없어도(개발/키 누락 배포) 같은 결제 식별자의 반복 충전은 막는다.
        # 금액 검증은 결제사 조회가 필요하므로 이 경로에서는 생략한다.
        if payment_ledger.is_used(req.imp_uid):
            raise HTTPException(status_code=409, detail="이미 처리된 결제입니다")
        payment_ledger.mark_used(req.imp_uid, user_id=user_id, points=req.points)

    user = user_store.purchase_points(user_id, req.points)
    if user is None:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없어요")
    return {"questions_left": user.credits_left}
