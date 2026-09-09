"""CoursePilot 백엔드 진입점.

실행: uvicorn app.main:app --reload
"""
from __future__ import annotations

import logging
import re
import secrets
from contextlib import asynccontextmanager
from time import monotonic

import socketio
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from app.adapters.map_service import get_map_service
from app.bookmarks import bookmark_store
from app.chat import ChatMessage, chat_store
from app.config import settings
from app.constants import DEFAULT_REGION, DEFAULT_START_TIME
from app.feedback import feedback_store
from app.middleware import RateLimitMiddleware, RequestLogMiddleware
from app.pipeline.agent import generate_course
from app.pipeline.decomposition import is_actionable, parse_constraints
from app.pipeline.edit import EditCommand, apply_edit, parse_edit
from app.popularity import popularity_store
from app.queue import queues
from app.ratings import rating_store
from app.realtime import (
    broadcast_lock,
    broadcast_message,
    broadcast_progress,
    broadcast_state,
    sio,
)
from app.schemas import Course, Place, PlanConstraints
from app.store import store
from app.users import CreditError, Preferences, user_store


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from app.db import init_db, set_ready

    set_ready(init_db())  # 전 스토어가 참조하는 단일 readiness
    yield


api = FastAPI(title="CoursePilot API", lifespan=lifespan)

MAX_COURSE_ITEMS = 50  # 코스 1개에 담을 수 있는 장소 상한(동선 재계산 비용·UI 가독성)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

# 순서 주의: 나중에 add 한 미들웨어가 바깥쪽 → rate limit 이 로깅보다 먼저 평가되도록
api.add_middleware(RequestLogMiddleware)
api.add_middleware(RateLimitMiddleware)
api.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@api.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    """예상 못 한 오류도 추적 가능한 응답으로. 내부 details 는 노출하지 않는다."""
    request_id = getattr(request.state, "request_id", "-")
    logging.getLogger("coursepilot").exception("[%s] unhandled error", request_id)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "일시적인 오류가 발생했어요. 잠시 후 다시 시도해주세요.",
            "request_id": request_id,
        },
        headers={"X-Request-Id": request_id},
    )


class GenerateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class SignupRequest(BaseModel):
    # 전화번호 인증은 별도 프로세스 가정, 여기선 인증 완료 후 호출
    phone: str = Field(min_length=9, max_length=20, pattern=r"^[0-9\-+ ]+$")
    referrer_id: str | None = Field(default=None, max_length=64)  # 9-4 레퍼럴

REFERRAL_BONUS = 1


@api.get("/health")
async def health() -> dict:
    return {"status": "ok"}


def _require_admin(token: str | None) -> None:
    """ADMIN_TOKEN 이 설정된 환경에서는 일치하는 헤더가 있어야 한다(미설정=개발용 개방).

    비교는 타이밍 공격을 피하려 상수 시간으로 한다.
    """
    if not settings.admin_token:
        logging.getLogger("coursepilot").warning(
            "ADMIN_TOKEN 미설정 — /admin/* 이 열려 있습니다(개발용). 배포 전 설정하세요."
        )
        return
    if token is None or not secrets.compare_digest(token, settings.admin_token):
        raise HTTPException(status_code=401, detail="관리자 토큰이 필요합니다")


@api.get("/admin/metrics")
async def admin_metrics(x_admin_token: str | None = Header(default=None)) -> dict:
    """엔드포인트별 요청 수·에러·지연(p50/p95). 인메모리, 인스턴스 단위."""
    _require_admin(x_admin_token)
    from app.metrics import metrics_store

    return metrics_store.snapshot()


@api.get("/admin/signals")
async def admin_signals(x_admin_token: str | None = Header(default=None)) -> dict:
    """학습 신호 관측(튜닝용). 축적된 피드백·전략·만족도 지표를 요약.

    개인정보 없이 집계값만 노출. 운영자 계수 튜닝·품질 모니터링에 사용.
    """
    _require_admin(x_admin_token)
    from app.feedback import feedback_store
    from app.outcome import outcome_store
    from app.strategy import strategy_store

    counts = feedback_store.counts()
    liked, disliked = counts.get("liked", 0), counts.get("disliked", 0)
    offered, applied = counts.get("relax_offered", 0), counts.get("relax_applied", 0)
    return {
        "feedback_counts": counts,
        "relax_acceptance_rate": feedback_store.acceptance_rate(),
        # 완화가 얼마나 자주 필요했는지(제안) 대비 실제 적용 비율
        "relax_offered": offered,
        "relax_applied": applied,
        # 만족도: 표본이 없으면 None(0으로 오해하지 않게)
        "satisfaction_rate": (liked / (liked + disliked)) if (liked + disliked) else None,
        "completed_count": counts.get("completed", 0),
        "seed_strategy_counts": strategy_store.counts(),
        "score_satisfaction_separation": outcome_store.separation(),
        # 온보딩 설문 응답률·분포(문항 수·문구 조정 근거)
        "preferences": user_store.preference_stats(),
    }


class SmsRequestBody(BaseModel):
    phone: str = Field(min_length=9, max_length=20, pattern=r"^[0-9\-+ ]+$")


class SmsVerifyBody(BaseModel):
    phone: str = Field(min_length=9, max_length=20, pattern=r"^[0-9\-+ ]+$")
    code: str = Field(min_length=6, max_length=6, pattern=r"^[0-9]{6}$")


@api.post("/auth/sms/request")
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


@api.post("/auth/sms/verify")
async def sms_verify(req: SmsVerifyBody) -> dict:
    from app.auth import verification_store

    ok = verification_store.verify(req.phone, req.code)
    if not ok:
        raise HTTPException(status_code=400, detail="인증번호가 올바르지 않거나 만료되었습니다")
    return {"verified": True}


@api.post("/signup")
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


@api.put("/users/{user_id}/preferences")
async def set_preferences(
    user_id: str, prefs: Preferences, x_user_id: str | None = Header(default=None)
) -> dict:
    _require_self(user_id, x_user_id)
    user = user_store.set_preferences(user_id, prefs)
    if user is None:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없어요")
    return {"ok": True}


@api.get("/users/{user_id}/preferences", response_model=Preferences)
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


@api.get("/users/{user_id}/credits")
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


@api.post("/users/{user_id}/purchase")
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


@api.post("/courses", response_model=Course)
async def create_course(x_user_id: str | None = Header(default=None)) -> Course:
    return store.create(owner_id=x_user_id)


@api.post("/courses/{course_id}/duplicate", response_model=Course)
async def duplicate_course(
    course_id: str, x_user_id: str | None = Header(default=None)
) -> Course:
    """코스 복제. 지난 코스를 원본을 건드리지 않고 다시 편집하고 싶을 때 쓴다.

    공유받은 코스도 복제할 수 있고, 사본의 생성자는 요청자다.
    """
    source = store.get(course_id)
    if source is None:
        raise HTTPException(status_code=404, detail="코스를 찾을 수 없어요")
    copy = source.model_copy(deep=True)
    copy.id = store.new_id()
    copy.owner_id = x_user_id
    copy.title = f"{source.title} (사본)"
    copy.locked = False
    store.save(copy)
    return copy


@api.get("/users/{user_id}/courses", response_model=list[Course])
async def my_courses(
    user_id: str, limit: int = 50, x_user_id: str | None = Header(default=None)
) -> list[Course]:
    """마이페이지: 내가 생성한 코스 히스토리 (9-4). 최근 limit 개."""
    _require_self(user_id, x_user_id)
    return store.list_by_owner(user_id, max(1, min(limit, 100)))


@api.get("/users/{user_id}/bookmarks", response_model=list[Course])
async def my_bookmarks(
    user_id: str, limit: int = 50, x_user_id: str | None = Header(default=None)
) -> list[Course]:
    _require_self(user_id, x_user_id)
    ids = bookmark_store.list_course_ids(user_id, max(1, min(limit, 100)))
    return store.get_many(ids)


BOOKMARK_WEIGHT = 2  # 북마크는 채택보다 강한 관심 신호


@api.put("/users/{user_id}/bookmarks/{course_id}")
async def add_bookmark(
    user_id: str, course_id: str, x_user_id: str | None = Header(default=None)
) -> dict:
    _require_self(user_id, x_user_id)
    course = store.get(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="코스를 찾을 수 없어요")
    added = bookmark_store.add(user_id, course_id)
    if added:
        # 북마크된 코스의 장소에 인기 가중(암묵적 정량 신호). 반복 호출로 부풀지 않게
        # 새로 담긴 경우에만 반영한다.
        popularity_store.bump_many([it.place.id for it in course.items], weight=BOOKMARK_WEIGHT)
    return {"ok": True, "added": added}


@api.delete("/users/{user_id}")
async def delete_account(
    user_id: str, x_user_id: str | None = Header(default=None)
) -> dict:
    """회원 탈퇴. 계정·전화번호·내 코스·북마크를 지운다(본인만).

    개인정보 삭제 요청을 코드로 처리할 수 있게 한다. 남는 것은 개인을 식별할 수
    없는 집계 신호(장소 인기 등)뿐이다.
    """
    _require_self(user_id, x_user_id)
    if user_store.get(user_id) is None:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없어요")
    my_courses = store.list_by_owner(user_id, limit=1000)
    for course in my_courses:
        store.delete(course.id)
        chat_store.clear(course.id)
    bookmark_store.remove_all(user_id)
    user_store.delete(user_id)
    return {"ok": True, "deleted_courses": len(my_courses)}


@api.delete("/users/{user_id}/bookmarks/{course_id}")
async def remove_bookmark(
    user_id: str, course_id: str, x_user_id: str | None = Header(default=None)
) -> dict:
    _require_self(user_id, x_user_id)
    removed = bookmark_store.remove(user_id, course_id)
    course = store.get(course_id)
    if removed and course is not None:
        # 북마크를 풀면 담을 때 준 가점을 되돌린다(신호가 한쪽으로만 쌓이지 않게)
        popularity_store.bump_many(
            [it.place.id for it in course.items], weight=-BOOKMARK_WEIGHT
        )
    return {"ok": True, "removed": removed}


class RenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=60)


@api.patch("/courses/{course_id}", response_model=Course)
async def rename_course(
    course_id: str, req: RenameRequest, x_user_id: str | None = Header(default=None)
) -> Course:
    """코스 이름 변경. 생성자가 있는 코스는 생성자만 변경할 수 있다."""
    course = _owned_course(course_id, x_user_id)
    course.title = req.title.strip()
    store.save(course)
    await broadcast_state(course_id, course.model_dump(mode="json"))
    return course


@api.delete("/courses/{course_id}")
async def delete_course(course_id: str, x_user_id: str | None = Header(default=None)) -> dict:
    """코스 삭제. 생성자가 있는 코스는 생성자만 삭제할 수 있다."""
    _owned_course(course_id, x_user_id)
    store.delete(course_id)
    return {"ok": True}


def _owned_course(course_id: str, user_id: str | None) -> Course:
    course = store.get(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="코스를 찾을 수 없어요")
    if course.owner_id is not None and course.owner_id != user_id:
        raise HTTPException(status_code=403, detail="코스 생성자만 변경할 수 있어요")
    return course


@api.get("/courses/{course_id}/calendar.ics")
async def course_calendar(course_id: str) -> Response:
    """코스를 캘린더 앱에 넣을 수 있는 .ics 로 내보낸다."""
    from app.calendar import to_ics

    course = store.get(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="코스를 찾을 수 없어요")
    filename = f"coursepilot-{course_id}.ics"
    return Response(
        content=to_ics(course, day=course.plan_date),
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@api.get("/courses/{course_id}", response_model=Course)
async def get_course(course_id: str) -> Course:
    course = store.get(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="코스를 찾을 수 없어요")
    return course


class ReviewSummaryRequest(BaseModel):
    place_id: str = Field(min_length=1, max_length=128)
    place_name: str = Field(min_length=1, max_length=200)
    query: str = Field(default="분위기 방문 후기", max_length=200)


SUMMARY_CACHE_TTL_SEC = 600  # 리뷰 요약 재사용 시간(같은 장소를 여러 번 열어도 1회 호출)
SUMMARY_CACHE_MAX = 500
_summary_cache: dict[tuple[str, str], tuple[float, dict]] = {}


def _summary_cache_get(key: tuple[str, str]) -> dict | None:
    hit = _summary_cache.get(key)
    if hit and monotonic() - hit[0] < SUMMARY_CACHE_TTL_SEC:
        return hit[1]
    return None


def _summary_cache_put(key: tuple[str, str], value: dict) -> None:
    now = monotonic()
    for stale in [k for k, (ts, _) in _summary_cache.items() if now - ts >= SUMMARY_CACHE_TTL_SEC]:
        del _summary_cache[stale]
    if len(_summary_cache) >= SUMMARY_CACHE_MAX:
        oldest = min(_summary_cache, key=lambda k: _summary_cache[k][0])
        del _summary_cache[oldest]
    _summary_cache[key] = (now, value)


@api.post("/reviews/summary")
async def review_summary(req: ReviewSummaryRequest) -> dict:
    """장소 상세 모달용 리뷰 요약 (4-2 + 8장 RAG). 같은 장소는 잠시 캐시한다."""
    cache_key = (req.place_id, req.query)
    cached = _summary_cache_get(cache_key)
    if cached is not None:
        return cached

    from app.db import is_ready
    from app.reviews.aspects import extract_aspects
    from app.reviews.rag import (
        fetch_filtered,
        ingest_place_reviews,
        retrieve,
        summarize_reviews,
    )

    db_ready = is_ready()
    if db_ready:
        found = await retrieve(req.place_id, req.query, db_ready=db_ready)
        if not found:
            # 최초 조회 시 수집 후 재검색
            await ingest_place_reviews(req.place_id, req.place_name, db_ready)
            found = await retrieve(req.place_id, req.query, db_ready=db_ready)
    else:
        # DB 미사용(개발): 수집+협찬 필터만 적용한 리뷰를 바로 요약
        found = await fetch_filtered(req.place_name)
    summary = await summarize_reviews(found)
    pros, cons = extract_aspects(found)
    result = {"summary": summary, "count": len(found), "pros": pros, "cons": cons}
    if found:  # 빈 결과는 캐시하지 않는다(수집 전일 수 있음)
        _summary_cache_put(cache_key, result)
    return result


@api.get("/courses/{course_id}/reasons")
async def course_reasons_endpoint(course_id: str) -> dict:
    """각 장소가 왜 들어갔는지 짧은 근거. 저장하지 않고 그때그때 계산한다."""
    course = store.get(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="코스를 찾을 수 없어요")
    last_text = next(
        (m.text for m in reversed(chat_store.list(course_id)) if m.role == "user"), ""
    )
    from app.reasons import course_reasons

    return {"reasons": course_reasons(course, last_text)}


class GenerateResponse(BaseModel):
    course: Course
    relaxed: bool  # 조건이 완화되었는지
    needs_confirmation: bool  # 완화로도 부족 → 사용자 확인 필요 (7-4)


@api.post("/courses/{course_id}/relax", response_model=GenerateResponse)
async def relax(course_id: str, x_user_id: str | None = Header(default=None)) -> GenerateResponse:
    """"조건을 완화해도 좋다"는 답변에 대한 재시도.

    직전 요청 문장을 그대로 다시 쓰되 완화를 강제한다. 사용자가 새 질문을 한 게
    아니므로 크레딧은 차감하지 않는다.
    """
    if x_user_id is None:
        raise HTTPException(status_code=403, detail="AI 챗봇은 생성자만 사용할 수 있습니다")
    _owned_course(course_id, x_user_id)  # 공유받은 사람이 남의 코스를 갈아엎지 못하게
    last_user_text = next(
        (m.text for m in reversed(chat_store.list(course_id)) if m.role == "user"), None
    )
    if last_user_text is None:
        raise HTTPException(status_code=400, detail="완화할 이전 요청이 없습니다")

    async def action() -> GenerateResponse:
        course = store.get(course_id)
        if course is None:
            raise HTTPException(status_code=404, detail="코스를 찾을 수 없어요")
        course.locked = True
        await broadcast_lock(course_id, True)
        # 완화 재시도에서도 온보딩 선호(지역·예산·식이)와 행동 선호를 그대로 쓴다 —
        # 예전에는 None 을 넘겨, 완화하면 사용자 프로필이 통째로 무시됐다.
        before_ids = [it.place.id for it in course.items]
        prefs: dict | None = None
        user = user_store.get(x_user_id)
        if user is not None:
            from app.behavior import behavior_store

            prefs = user.preferences.model_dump()
            prefs["behavior_cats"] = behavior_store.top_categories(x_user_id)
        try:
            result = await generate_course(
                last_user_text, get_map_service(), prefs, None, force_relax=True
            )
            course.items = result.timeline
            if result.constraints.region:
                course.region = result.constraints.region
            if result.constraints.plan_date:
                course.plan_date = result.constraints.plan_date
            if result.constraints.party_size:
                course.party_size = result.constraints.party_size
        finally:
            course.locked = False
            store.save(course)
            await broadcast_lock(course_id, False)
        if [it.place.id for it in course.items] == before_ids:
            # 완화해도 결과가 같으면 같은 문구를 반복하지 않고 다음 수를 제안한다
            ai_text = (
                "완화해도 더 찾지 못했어요. 지역이나 시간대를 바꿔 보시겠어요?"
            )
        else:
            ai_text = _ai_reply(
                course, True, result.needs_confirmation, constraints=result.constraints
            )
        chat_store.append(course_id, "ai", ai_text)
        await broadcast_state(course_id, course.model_dump(mode="json"))
        await broadcast_message(course_id, "ai", ai_text)
        return GenerateResponse(
            course=course, relaxed=True, needs_confirmation=result.needs_confirmation
        )

    return await queues.run(course_id, action)


@api.post("/courses/{course_id}/generate", response_model=GenerateResponse)
async def generate(
    course_id: str,
    req: GenerateRequest,
    x_user_id: str | None = Header(default=None),
) -> GenerateResponse:
    """챗봇 명령: AI 파이프라인 실행. 액션 큐 직렬화 + Lock broadcast.

    AI 명령은 생성자(로그인 회원)만 가능하며 크레딧 1회 차감(9-3).
    참여자(비로그인)는 수동 편집만 가능 → 403.
    """
    # 존재 확인은 큐 밖에서 빠르게(단, 실제 상태는 lock 안에서 재조회한다)
    if x_user_id is None:
        raise HTTPException(status_code=403, detail="AI 챗봇은 생성자만 사용할 수 있습니다")
    _owned_course(course_id, x_user_id)  # 생성자만 AI 명령 가능(참여자는 수동 편집만)

    async def action() -> GenerateResponse:
        # 최신 상태를 lock 안에서 재조회 → 동시 요청 간 lost update 방지
        course = store.get(course_id)
        if course is None:
            raise HTTPException(status_code=404, detail="코스를 찾을 수 없어요")

        # 크레딧 소비도 lock 안에서: 원자적 차감 + 실패 시 환불
        try:
            user = user_store.consume_credit(x_user_id)
        except CreditError:
            raise HTTPException(
                status_code=402, detail="AI에게 질문하려면 포인트를 구매해주세요"
            ) from None
        prefs = user.preferences.model_dump()
        # 행동 선호(#13): 이 사용자가 실제 자주 채택한 카테고리를 스코어링에 주입
        from app.behavior import behavior_store

        prefs["behavior_cats"] = behavior_store.top_categories(x_user_id)

        course.locked = True
        await broadcast_lock(course_id, True)
        chat_store.append(course_id, "user", req.text)  # append-only 로그
        await broadcast_message(course_id, "user", req.text)

        async def on_progress(stage: str) -> None:
            await broadcast_progress(course_id, stage)

        relaxed = False
        needs_confirmation = False
        is_edit = False
        region_guessed = False  # 지역을 못 알아들어 기본 지역으로 만든 경우
        pref_region: str | None = None  # 선호 프로필로 지역을 채운 경우
        gen_constraints: PlanConstraints | None = None  # 편집 명령이면 None
        old_ids = [it.place.id for it in course.items]
        edit_cmd = parse_edit(req.text) if course.items else EditCommand(action="none")
        # 질문("여기 주차 되나요?")에 코스를 갈아엎지 않는다. 편집 명령이 아닌
        # 물음이면 지금 코스로 답하고 크레딧도 돌려준다.
        if edit_cmd.action == "none" and course.items and _is_question(req.text):
            user_store.refund_credit(x_user_id)
            course.locked = False
            await broadcast_lock(course_id, False)
            ai_text = _course_answer(course)
            chat_store.append(course_id, "ai", ai_text)
            await broadcast_message(course_id, "ai", ai_text)
            return GenerateResponse(course=course, relaxed=False, needs_confirmation=False)
        if edit_cmd.action == "clarify":
            # 어느 자리를 바꿀지 알 수 없다 → 새 코스를 만들지 않고 되묻는다
            user_store.refund_credit(x_user_id)
            course.locked = False
            await broadcast_lock(course_id, False)
            ai_text = "어느 자리를 바꿀까요? 순번(예: 2번째)이나 장소 종류로 말씀해 주세요."
            chat_store.append(course_id, "ai", ai_text)
            await broadcast_message(course_id, "ai", ai_text)
            return GenerateResponse(course=course, relaxed=False, needs_confirmation=False)
        # 편집도 아니고 조건·의도도 없는 입력("ㅋㅋㅋ")으로 엉뚱한 코스를 만들고
        # 크레딧까지 태우지 않는다 — 무엇을 원하는지 되묻는다.
        if edit_cmd.action == "none" and not is_actionable(
            req.text, parse_constraints(req.text)
        ):
            user_store.refund_credit(x_user_id)
            course.locked = False
            await broadcast_lock(course_id, False)
            ai_text = '어떤 모임인지 알려주세요. 예: "성수동에서 토요일 저녁 데이트"'
            chat_store.append(course_id, "ai", ai_text)
            await broadcast_message(course_id, "ai", ai_text)
            return GenerateResponse(course=course, relaxed=False, needs_confirmation=False)
        try:
            if edit_cmd.action != "none":
                # 부분 수정: 해당 카드만 교체/삭제 후 전체 동선 재계산 (4-3)
                is_edit = True
                await on_progress("editing")
                course.items = await apply_edit(course, edit_cmd, get_map_service())
            else:
                result = await generate_course(req.text, get_map_service(), prefs, on_progress)
                course.items = result.timeline
                relaxed = result.relaxed
                needs_confirmation = result.needs_confirmation
                gen_constraints = result.constraints
                region_guessed = result.constraints.region is None
                # 문장에 지역이 없어 저장된 선호로 채웠다면 그 사실을 알린다
                if (
                    result.constraints.region
                    and parse_constraints(req.text).region is None
                    and prefs.get("region") == result.constraints.region
                ):
                    pref_region = result.constraints.region
                if result.constraints.region:
                    course.region = result.constraints.region
                if result.constraints.plan_date:  # 캘린더 내보내기 기준일
                    course.plan_date = result.constraints.plan_date
                if result.constraints.party_size:
                    course.party_size = result.constraints.party_size
                # #17: 생성 시 코스 목적함수 점수 저장(만족도 대조용)
                from app.pipeline.planner import course_score

                course.predicted_score = course_score(course.items)
        except Exception:
            user_store.refund_credit(x_user_id)  # 실패 시 소비 크레딧 되돌림
            course.locked = False
            await broadcast_lock(course_id, False)
            raise
        finally:
            course.locked = False
        store.save(course)
        new_ids = [it.place.id for it in course.items]
        # 코스에 채택된 장소에 인기 가점(암묵적 정량 신호)
        popularity_store.bump_many(new_ids)
        # 시간대 컨텍스트(#12): 코스 시작 시간대에 채택 신호 누적
        if not is_edit and course.items:
            from app.timecontext import daypart_of, time_context_store

            first = course.items[0].arrive
            if first:
                time_context_store.bump_many(new_ids, daypart_of(first.hour))
        # 행동 선호(#13): 채택된 장소의 카테고리를 사용자 행동 프로필에 누적
        if course.items:
            from app.pipeline.planner import classify

            behavior_store.bump(x_user_id, [classify(it.place) for it in course.items])
        # 협업 필터링(활용): 함께 채택된 장소 쌍 공동 채택 누적
        if len(new_ids) >= 2:
            from app.cooccurrence import cooccurrence_store

            cooccurrence_store.bump_course(new_ids)
        # 전역 장소 저장소: 등장 장소 스냅샷 보관(CF 추천 id→장소 복원용)
        if course.items:
            from app.places import place_repo

            place_repo.upsert_many([it.place for it in course.items])
        # 피드백(#16): 완화 제안/적용 로깅
        if needs_confirmation:
            feedback_store.log(course_id, "relax_offered")
        elif relaxed:
            feedback_store.log(course_id, "relax_applied")
        # 생존율(#3): AI 편집으로 교체/삭제돼 밀려난 장소는 -1 로 상쇄(추천 미적중)
        if is_edit:
            dropped = [pid for pid in old_ids if pid not in set(new_ids)]
            popularity_store.bump_many(dropped, weight=-1)

        if is_edit and edit_cmd.action == "clear":
            ai_text = "코스를 비웠어요. 어떤 모임인지 다시 말씀해 주세요."
        elif is_edit and new_ids == old_ids and edit_cmd.action == "reorder":
            # 이미 최적 동선이면 "못 찾았다"가 아니라 그대로 좋다고 알린다
            user_store.refund_credit(x_user_id)
            ai_text = "이미 이동거리가 가장 짧은 순서예요. 그대로 두는 걸 추천해요."
        elif is_edit and new_ids == old_ids:
            # 없는 순번·카테고리를 지목하면 아무것도 바뀌지 않는다 → 알리고 크레딧도 돌려준다
            user_store.refund_credit(x_user_id)
            ai_text = "요청하신 자리를 찾지 못했어요. 순번(예: 2번째)이나 장소 종류로 다시 말씀해 주세요."
        elif is_edit and edit_cmd.action in ("replace", "remove", "add"):
            ai_text = _edit_reply(course, edit_cmd.action, old_ids, new_ids)
        elif is_edit and edit_cmd.action in ("reorder", "swap"):
            # 순서만 바꾼 경우엔 "N곳으로 구성했어요" 대신 무엇이 달라졌는지 말한다
            total = sum(
                it.travel_to_next.duration_min for it in course.items if it.travel_to_next
            )
            order = " → ".join(it.place.name for it in course.items)
            ai_text = f"순서를 바꿨어요. {order} (총 이동 {total}분)"
        else:
            ai_text = _ai_reply(
                course,
                relaxed,
                needs_confirmation,
                region_guessed,
                gen_constraints,
                pref_region,
            )
        chat_store.append(course_id, "ai", ai_text)
        await broadcast_state(course_id, course.model_dump(mode="json"))
        await broadcast_message(course_id, "ai", ai_text)
        await broadcast_lock(course_id, False)
        return GenerateResponse(
            course=course, relaxed=relaxed, needs_confirmation=needs_confirmation
        )

    return await queues.run(course_id, action)


_QUESTION_RE = re.compile(r"[?？]\s*$|나요|까요|어때|얼마나|있나|없나|맞나|되나|뭐야|어디야")


def _is_question(text: str) -> bool:
    """코스를 바꾸라는 지시가 아니라 물음인지."""
    return bool(_QUESTION_RE.search(text.strip()))


def _course_answer(course: Course) -> str:
    """지금 코스로 답할 수 있는 것(개수·시작·종료·이동)을 요약해 답한다."""
    n = len(course.items)
    first, last = course.items[0], course.items[-1]
    travel = sum(it.travel_to_next.duration_min for it in course.items if it.travel_to_next)
    parts = [f"지금 코스는 {n}곳이에요"]
    if first.arrive and last.depart:
        parts.append(
            f"{first.arrive.strftime('%H:%M')}에 시작해 {last.depart.strftime('%H:%M')}쯤 끝나요"
        )
    if travel:
        parts.append(f"이동은 모두 {travel}분")
    return (
        ". ".join(parts)
        + ". 장소별 영업시간·리뷰는 카드를 누르면 볼 수 있어요."
    )


def _edit_reply(course: Course, action: str, old_ids: list[str], new_ids: list[str]) -> str:
    """편집 결과를 무엇이 바뀌었는지로 알린다("3곳으로 구성했어요"는 편집엔 무의미)."""
    names = {it.place.id: it.place.name for it in course.items}
    added = [pid for pid in new_ids if pid not in old_ids]
    removed = [pid for pid in old_ids if pid not in new_ids]
    n = len(course.items)
    if action == "add" and added:
        return f"'{names.get(added[0], '새 장소')}'를 마지막에 추가했어요. 이제 {n}곳이에요."
    if action == "remove" and removed:
        return f"한 곳을 뺐어요. 이제 {n}곳이에요."
    if action == "replace" and added:
        order = new_ids.index(added[0]) + 1
        return f"{order}번째를 '{names.get(added[0], '다른 곳')}'으로 바꿨어요."
    return f"수정했어요. 이제 {n}곳이에요."


def _ai_reply(
    course: Course,
    relaxed: bool,
    needs_confirmation: bool,
    region_guessed: bool = False,
    constraints: PlanConstraints | None = None,
    pref_region: str | None = None,
) -> str:
    n = len(course.items)
    if needs_confirmation:
        # 왜 부족한지 짚어 줘야 무엇을 바꿀지 알 수 있다("완화할까요?"만으로는 막막하다)
        hour = constraints.start_time.hour if constraints and constraints.start_time else None
        if n == 0 and hour is not None and (hour >= 23 or hour < 6):
            return (
                f"{hour}시에는 문 연 곳을 찾기 어려워요. "
                "시간을 조금 당기거나 다른 지역으로 바꿔 볼까요?"
            )
        if n == 0 and constraints is not None and constraints.budget_max:
            budget = constraints.budget_max
            amount = f"{budget // 10000}만원" if budget >= 10000 else f"{budget:,}원"
            return (
                f"1인 {amount} 안에서 맞는 곳을 찾지 못했어요. "
                "예산을 올리거나 조건을 완화할까요?"
            )
        if n == 0:
            return "조건에 맞는 장소를 찾지 못했어요. 지역이나 시간을 바꿔 볼까요?"
        return f"{n}곳까지만 찾았어요. 조건을 완화할까요?"
    # 무엇을 알아들었는지 먼저 되짚어 준다(잘못 알아들었으면 바로 정정 가능)
    parts: list[str] = []
    if course.plan_date:
        parts.append(f"{course.plan_date.month}월 {course.plan_date.day}일")
    first = course.items[0] if course.items else None
    if first is not None and first.arrive is not None:
        parts.append(f"{first.arrive.strftime('%H:%M')} 시작")
    if constraints is not None and constraints.start_place:
        parts.append(f"{constraints.start_place} 출발")
    prefix = f"{' '.join(parts)}, " if parts else ""
    base = f"{prefix}{n}곳으로 코스를 구성했어요."
    # 언제 끝나는지 미리 알려주면 일정 조정을 바로 할 수 있다
    last = course.items[-1] if course.items else None
    if last is not None and last.depart is not None:
        base += f" {last.depart.strftime('%H:%M')}쯤 마무리돼요."
    if constraints is not None and constraints.prefer_indoor:
        base += " 비 예보라 실내 위주로 골랐어요."
    if relaxed:
        base += " 일부 조건은 완화했어요."
    if pref_region:
        # 사용자가 지역을 말하지 않아 선호 설정 값을 썼다는 것을 드러낸다
        base += f" 설정하신 {pref_region} 기준으로 만들었어요."
    if region_guessed:
        # 지역을 못 알아들으면 기본 지역으로 만들어지므로, 조용히 넘어가지 않고 알린다.
        base += f" 지역을 못 알아들어 {course.region or DEFAULT_REGION} 기준으로 만들었어요."
    return base


class RatingRequest(BaseModel):
    stars: int = Field(ge=1, le=5)


@api.post("/places/{place_id}/rating")
async def rate_place(
    place_id: str, req: RatingRequest, x_user_id: str | None = Header(default=None)
) -> dict:
    """장소 원탭 별점(1~5). 자체 정량 신호로 planner 스코어에 반영 (data #9).

    같은 사람이 다시 매기면 표본을 늘리지 않고 이전 점수를 대체한다
    (반복 제출로 평균을 흔들 수 없게).
    """
    from app.ratings import user_rating_store

    if x_user_id:
        previous = user_rating_store.previous(x_user_id, place_id)
        if previous == req.stars:
            avg_same = rating_store.averages([place_id]).get(place_id)
            return {"ok": True, "average": avg_same, "counted": False}
        rating_store.submit(place_id, req.stars, replaces=previous)
        user_rating_store.remember(x_user_id, place_id, req.stars)
    else:
        rating_store.submit(place_id, req.stars)
    avg = rating_store.averages([place_id]).get(place_id)
    return {"ok": True, "average": avg}


REVISIT_WEIGHT = 2  # 재방문 의사는 장소 단위 강한 긍정(또 가고 싶다)


@api.post("/places/{place_id}/revisit")
async def mark_revisit(
    place_id: str, x_user_id: str | None = Header(default=None)
) -> dict:
    """재방문 의사 토글 (data #10). "또 가고 싶어요" → 장소 인기 강한 가점.

    한 사람이 한 장소에 한 번만 의미가 있는 명시 신호라, 사용자·장소 단위로
    중복을 막는다. 로그인하지 않으면 신호로 세지 않는다(반복 호출로 부풀리기 방지).
    """
    from app.revisits import revisit_store

    if not x_user_id:
        return {"ok": True, "counted": False}
    if not revisit_store.mark(x_user_id, place_id):
        return {"ok": True, "counted": False}
    popularity_store.bump(place_id, weight=REVISIT_WEIGHT)
    return {"ok": True, "counted": True}


class FeedbackRequest(BaseModel):
    kind: str = Field(min_length=1, max_length=40)
    detail: str = Field(default="", max_length=200)


@api.post("/courses/{course_id}/feedback")
async def post_feedback(course_id: str, req: FeedbackRequest) -> dict:
    """사용자 피드백 기록(#15/#16). 예: 완화 수락/거부."""
    if store.get(course_id) is None:
        raise HTTPException(status_code=404, detail="코스를 찾을 수 없어요")
    feedback_store.log(course_id, req.kind, req.detail)
    return {"ok": True}


VIEW_WEIGHT = 0.2  # 공유 열람은 약한 완성도 대리 신호(다수 열람 → 완성도 방증)


@api.post("/courses/{course_id}/view")
async def view_course(course_id: str) -> dict:
    """공유 열람 신호 (data #5). 공유 뷰가 열릴 때 코스 장소에 약한 가점.

    완성도 대리지표(열람 많을수록 잘 만든 코스일 가능성). 인증 불필요.
    """
    course = store.get(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="코스를 찾을 수 없어요")
    if course.viewed:
        # 새로고침으로 열람 신호를 계속 불릴 수 없게 코스당 한 번만 반영한다
        return {"ok": True, "already": True}
    popularity_store.bump_many([it.place.id for it in course.items], weight=VIEW_WEIGHT)
    course.viewed = True
    store.save(course)
    return {"ok": True, "already": False}


@api.get("/places/{place_id}/related", response_model=list[Place])
async def related_places(place_id: str, limit: int = 5) -> list[Place]:
    """함께 가요 추천 (협업 필터링). 이 장소와 자주 함께 채택된 장소들.

    데이터가 없으면 빈 목록(콜드스타트 안전). 인증 불필요.
    """
    from app.cooccurrence import cooccurrence_store
    from app.places import place_repo

    limit = max(1, min(limit, 20))
    partners = cooccurrence_store.top_partners(place_id, limit)
    resolved = place_repo.get_many([pid for pid, _ in partners])
    found = [resolved[pid] for pid, _ in partners if pid in resolved]
    if found:
        return found
    # 콜드스타트: 공동채택 이력이 없으면 근처 인기 장소로 폴백
    return _nearby_popular(place_id, limit)


NEARBY_DEGREES = 0.02  # 위경도 약 2km 이내(정렬용 근사)


def _nearby_popular(place_id: str, limit: int) -> list[Place]:
    """같은 동네의 인기 장소. 기준 장소를 모르면 빈 목록."""
    from app.places import place_repo

    known = place_repo.get_many([place_id]).get(place_id)
    if known is None:
        return []
    candidates = [
        p
        for p in place_repo.all()
        if p.id != place_id
        and abs(p.lat - known.lat) <= NEARBY_DEGREES
        and abs(p.lng - known.lng) <= NEARBY_DEGREES
    ]
    if not candidates:
        return []
    scores = popularity_store.scores([p.id for p in candidates])
    candidates.sort(key=lambda p: (-scores.get(p.id, 0.0), -(p.rating or 0.0)))
    return candidates[:limit]


COMPLETION_WEIGHT = 3  # 완주(실제 방문)는 채택/북마크보다 강한 긍정 신호


@api.post("/courses/{course_id}/complete")
async def complete_course(course_id: str) -> dict:
    """완주 신호("다녀왔어요") (data #6). 실제 방문한 코스의 장소에 강한 인기 가점.

    비로그인 참여자도 누를 수 있어 인증/크레딧 불필요.
    """
    course = store.get(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="코스를 찾을 수 없어요")
    place_ids = [it.place.id for it in course.items]
    if course.completed:
        # 버튼을 여러 번 눌러도 신호가 배로 쌓이지 않게 한 번만 반영한다
        return {"ok": True, "places": len(place_ids), "already": True}
    popularity_store.bump_many(place_ids, weight=COMPLETION_WEIGHT)
    feedback_store.log(course_id, "completed", detail=f"{len(place_ids)}곳")
    course.completed = True
    store.save(course)
    return {"ok": True, "places": len(place_ids), "already": False}


SATISFACTION_WEIGHT = 2  # 완료 후 만족(👍)/불만족(👎) 원탭 평가 가중


class SatisfactionRequest(BaseModel):
    liked: bool  # 👍=True / 👎=False


@api.post("/courses/{course_id}/satisfaction")
async def rate_satisfaction(course_id: str, req: SatisfactionRequest) -> dict:
    """완료 후 원탭 만족도 👍/👎 (data #8). 텍스트 아님 → 광고·약관 무관.

    만족이면 코스 장소에 +가점, 불만족이면 -가점. 인증 불필요.
    """
    course = store.get(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="코스를 찾을 수 없어요")
    if course.satisfaction is req.liked:
        # 같은 평가를 반복해도 신호가 쌓이지 않게 한다
        return {"ok": True, "already": True}
    place_ids = [it.place.id for it in course.items]
    if course.satisfaction is not None:
        # 평가를 바꾼 경우: 이전 평가 효과를 먼저 되돌린다
        undo = -SATISFACTION_WEIGHT if course.satisfaction else SATISFACTION_WEIGHT
        popularity_store.bump_many(place_ids, weight=undo)
    weight = SATISFACTION_WEIGHT if req.liked else -SATISFACTION_WEIGHT
    popularity_store.bump_many(place_ids, weight=weight)
    feedback_store.log(course_id, "liked" if req.liked else "disliked")
    course.satisfaction = req.liked
    store.save(course)
    # #17: 예측 점수 vs 실제 만족도 대조 데이터 축적
    if course.predicted_score is not None:
        from app.outcome import outcome_store

        outcome_store.record(course.predicted_score, req.liked)
    return {"ok": True, "already": False}


def _reject_duplicates(place_ids: list[str]) -> None:
    """같은 장소가 두 번 들어가면 이동시간 0 구간과 신호 왜곡이 생긴다."""
    if len(set(place_ids)) != len(place_ids):
        raise HTTPException(status_code=400, detail="같은 장소를 두 번 담을 수 없어요")


class ReorderRequest(BaseModel):
    # 원하는 최종 순서. 빠진 id 는 삭제로 처리.
    place_ids: list[str] = Field(max_length=MAX_COURSE_ITEMS)


@api.post("/courses/{course_id}/reorder", response_model=Course)
async def manual_reorder(course_id: str, req: ReorderRequest) -> Course:
    """수동 편집(드래그/삭제). AI 미호출·무료지만 서버 큐로 직렬화 + broadcast (5-1).

    참여자(비로그인)도 가능하므로 인증/크레딧 불필요.
    """
    _reject_duplicates(req.place_ids)
    if store.get(course_id) is None:
        raise HTTPException(status_code=404, detail="코스를 찾을 수 없어요")

    async def action() -> Course:
        course = store.get(course_id)
        if course is None:
            raise HTTPException(status_code=404, detail="코스를 찾을 수 없어요")
        if course.locked:
            raise HTTPException(status_code=409, detail="AI 처리 중에는 편집할 수 없습니다")

        from app.pipeline.edit import _infer_mode
        from app.pipeline.validation import recompute

        by_id = {it.place.id: it for it in course.items}
        kept_ids = {pid for pid in req.place_ids if pid in by_id}
        # 생존율(#3/#4): 수동 삭제로 빠진 장소는 -1 상쇄(사용자 거부 신호)
        dropped = [pid for pid in by_id if pid not in kept_ids]
        ordered = [by_id[pid] for pid in req.place_ids if pid in by_id]
        if ordered:
            # 앵커는 코스의 원래 시작 시각(전체 최소 도착시각) — 순서가 바뀌어도 유지.
            arrivals = [it.arrive for it in course.items if it.arrive]
            start = min(arrivals) if arrivals else DEFAULT_START_TIME
            course.items = await recompute(
                [it.place for it in ordered], start, _infer_mode(ordered), get_map_service()
            )
        else:
            course.items = []
        store.save(course)
        popularity_store.bump_many(dropped, weight=-1)
        # 재정렬 패턴(#7): 사용자가 확정한 순서의 카테고리 전이를 선호로 학습
        if len(course.items) >= 2:
            from app.pipeline.planner import classify
            from app.sequence import sequence_store

            sequence_store.bump_sequence([classify(it.place) for it in course.items])
        await broadcast_state(course_id, course.model_dump(mode="json"))
        return course

    return await queues.run(course_id, action)


class AddPlaceRequest(BaseModel):
    place_id: str = Field(min_length=1, max_length=128)


@api.post("/courses/{course_id}/places", response_model=Course)
async def add_place(course_id: str, req: AddPlaceRequest) -> Course:
    """추천("함께 가요") 장소를 코스 끝에 추가 후 전체 동선 재계산 (수동 편집).

    장소는 전역 저장소에서 복원. AI 미호출·무료. 참여자도 가능하므로 인증 불필요.
    """
    if store.get(course_id) is None:
        raise HTTPException(status_code=404, detail="코스를 찾을 수 없어요")

    async def action() -> Course:
        course = store.get(course_id)
        if course is None:
            raise HTTPException(status_code=404, detail="코스를 찾을 수 없어요")
        if course.locked:
            raise HTTPException(status_code=409, detail="AI 처리 중에는 편집할 수 없습니다")
        if any(it.place.id == req.place_id for it in course.items):
            raise HTTPException(status_code=409, detail="이미 코스에 포함된 장소입니다")
        if len(course.items) >= MAX_COURSE_ITEMS:
            raise HTTPException(
                status_code=409, detail=f"한 코스에는 최대 {MAX_COURSE_ITEMS}곳까지 담을 수 있어요"
            )

        from app.places import place_repo

        resolved = place_repo.get_many([req.place_id])
        place = resolved.get(req.place_id)
        if place is None:
            raise HTTPException(status_code=404, detail="장소를 찾을 수 없어요")

        from app.pipeline.edit import _infer_mode
        from app.pipeline.validation import recompute

        places = [it.place for it in course.items] + [place]
        arrivals = [it.arrive for it in course.items if it.arrive]
        start = min(arrivals) if arrivals else DEFAULT_START_TIME
        course.items = await recompute(
            places, start, _infer_mode(course.items), get_map_service()
        )
        store.save(course)
        popularity_store.bump(req.place_id)  # 채택 신호
        await broadcast_state(course_id, course.model_dump(mode="json"))
        return course

    return await queues.run(course_id, action)


class SetItemsRequest(BaseModel):
    """코스 구성을 place_ids 로 통째로 설정. 추가·삭제·재정렬·되돌리기를 모두 커버한다."""

    place_ids: list[str] = Field(max_length=MAX_COURSE_ITEMS)


@api.post("/courses/{course_id}/items", response_model=Course)
async def set_items(course_id: str, req: SetItemsRequest) -> Course:
    """코스 항목을 지정한 순서로 설정 후 동선 재계산 (수동 편집).

    현재 코스에 없는 id 는 전역 장소 저장소에서 복원하므로, 삭제한 장소를 되살리는
    되돌리기(undo)도 이 엔드포인트 하나로 처리된다. AI 미호출·무료.
    """
    _reject_duplicates(req.place_ids)
    if store.get(course_id) is None:
        raise HTTPException(status_code=404, detail="코스를 찾을 수 없어요")

    async def action() -> Course:
        course = store.get(course_id)
        if course is None:
            raise HTTPException(status_code=404, detail="코스를 찾을 수 없어요")
        if course.locked:
            raise HTTPException(status_code=409, detail="AI 처리 중에는 편집할 수 없습니다")

        from app.places import place_repo

        current = {it.place.id: it.place for it in course.items}
        missing = [pid for pid in req.place_ids if pid not in current]
        restored = place_repo.get_many(missing) if missing else {}
        places = [current.get(pid) or restored.get(pid) for pid in req.place_ids]
        unknown = [pid for pid, p in zip(req.place_ids, places, strict=True) if p is None]
        if unknown:
            raise HTTPException(status_code=404, detail=f"알 수 없는 장소: {unknown[0]}")

        from app.pipeline.edit import _infer_mode
        from app.pipeline.validation import recompute

        arrivals = [it.arrive for it in course.items if it.arrive]
        start = min(arrivals) if arrivals else DEFAULT_START_TIME
        dropped = [pid for pid in current if pid not in set(req.place_ids)]
        course.items = (
            await recompute(
                [p for p in places if p is not None], start, _infer_mode(course.items), get_map_service()
            )
            if places
            else []
        )
        store.save(course)
        popularity_store.bump_many(dropped, weight=-1)  # 생존율(#3): 빠진 장소 상쇄
        await broadcast_state(course_id, course.model_dump(mode="json"))
        return course

    return await queues.run(course_id, action)


@api.get("/places/search", response_model=list[Place])
async def search_places(region: str, q: str = "", limit: int = 8) -> list[Place]:
    """장소 검색 (직접 추가·교체용). 결과는 전역 저장소에 보관해 이후 id 로 복원 가능.

    인증 불필요(수동 편집 보조). region 은 필수, q 는 추가 키워드.
    """
    region = region.strip()
    if not region:
        raise HTTPException(status_code=400, detail="지역을 입력해주세요")
    limit = max(1, min(limit, 20))
    keywords = [w for w in q.split() if w]
    places = await get_map_service().search_places(region, keywords, limit)

    from app.places import place_repo

    place_repo.upsert_many(places)  # 검색 결과를 id 로 추가할 수 있게 보관
    return places


@api.get("/courses/{course_id}/messages", response_model=list[ChatMessage])
async def get_messages(course_id: str) -> list[ChatMessage]:
    """채팅 로그 조회 (append-only). 공유 뷰에서는 노출하지 않음."""
    return chat_store.list(course_id)


# Socket.IO 를 FastAPI 에 마운트한 ASGI 앱
app = socketio.ASGIApp(sio, other_asgi_app=api)
