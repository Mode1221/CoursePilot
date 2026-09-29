"""픽앤어스(PickNuS) 백엔드 진입점.

실행: uvicorn app.main:app --reload
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from time import monotonic

import socketio
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from app.accounts_api import _require_self, accounts_router
from app.adapters.map_service import get_map_service
from app.admin_api import admin_router
from app.bookmarks import bookmark_store
from app.chat import chat_store
from app.chat_api import _owned_course, chat_router
from app.config import settings
from app.constants import DEFAULT_START_TIME
from app.identity import course_editor, require_caller, resolve_caller
from app.middleware import RateLimitMiddleware, RequestLogMiddleware, client_ip
from app.popularity import popularity_store
from app.queue import QueueOverflow, queues
from app.realtime import broadcast_state, sio
from app.schemas import Course, Place
from app.signals_api import signals_router
from app.store import store
from app.together_api import together_router
from app.usage import UsageDenied, charge
from app.users import user_store

# 개발 기본값 그대로면 비밀번호를 설정하지 않은 것으로 본다
_DEV_DB_PASSWORD = "coursepilot:coursepilot@"


_MIN_SECRET_LEN = 32
_PLACEHOLDER_WORDS = ("change", "example", "secret", "password", "test", "xxx")


def _weak_secret(value: str) -> bool:
    """운영 시크릿으로 못 쓰는 값: 비었거나, 32자 미만이거나, 예시 문구가 들어 있다."""
    v = value.strip()
    if len(v) < _MIN_SECRET_LEN:
        return True
    lowered = v.lower()
    return any(w in lowered for w in _PLACEHOLDER_WORDS)


def _production_warnings() -> list[str]:
    """운영에서 비어 있으면 안 되는 설정을 모은다(값은 절대 로그에 남기지 않는다)."""
    missing = []
    # 비어 있지 않아도 짧거나 예시 값이면 없는 것과 같다(추측·사전 공격으로 뚫린다).
    if _weak_secret(settings.session_secret):
        missing.append("SESSION_SECRET")  # 없으면 id 헤더만으로 남의 계정이 된다
    if _weak_secret(settings.admin_token):
        missing.append("ADMIN_TOKEN")  # 없으면 /admin/* 이 열린다
    if _DEV_DB_PASSWORD in settings.database_url:
        missing.append("POSTGRES_PASSWORD")  # 개발 기본 비밀번호를 그대로 쓰고 있다
    return missing


class ProductionConfigError(RuntimeError):
    """운영 필수 설정이 없다. 반쯤 열린 채로 뜨느니 기동을 멈춘다."""


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from app.db import init_db, set_ready

    if settings.is_production:
        # 경고만 남기고 뜨면 아무도 안 본다. 열린 채로 서비스되는 것보다 낫다.
        missing = _production_warnings()
        if missing:
            raise ProductionConfigError(
                f"운영 필수 설정이 없습니다: {', '.join(missing)}. "
                "ENV(APP_ENV)=production 에서는 이 값들이 반드시 있어야 합니다."
            )
    set_ready(init_db())  # 전 스토어가 참조하는 단일 readiness
    if settings.is_production and settings.sms_dev_fallback and not settings.sms_enabled:
        logging.getLogger("coursepilot").warning(
            "SMS_DEV_FALLBACK=true — 인증번호가 응답에 그대로 노출됩니다. "
            "누구나 남의 번호로 가입할 수 있으니 지인 테스트 기간에만 쓰고, 공개 전에 끄세요."
        )

    # 폐업 대장은 수백 MB다. 첫 요청에서 지연 로드하면 그 사용자가 수십 초를
    # 기다린다 → 기동 직후 백그라운드로 채우고, 채워지기 전에는 필터가 무동작.
    from app.adapters.localdata import localdata_refresher

    warm = asyncio.create_task(localdata_refresher())
    try:
        yield
    finally:
        warm.cancel()


api = FastAPI(title="PickNuS API", lifespan=lifespan)

MAX_COURSE_ITEMS = 50  # 코스 1개에 담을 수 있는 장소 상한(동선 재계산 비용·UI 가독성)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

# 순서 주의: 나중에 add 한 미들웨어가 바깥쪽 → rate limit 이 로깅보다 먼저 평가되도록
api.add_middleware(RequestLogMiddleware)
api.add_middleware(RateLimitMiddleware, limit=settings.rate_limit_per_min)
api.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@api.exception_handler(QueueOverflow)
async def queue_overflow(_request: Request, _exc: QueueOverflow) -> JSONResponse:
    """연타로 큐가 밀린 경우. 앞선 요청은 그대로 처리되므로 잠시 뒤 다시 보내면 된다."""
    return JSONResponse(
        status_code=429,
        content={"detail": "요청이 밀려 있어요. 잠시 후 다시 시도해주세요."},
    )


@api.middleware("http")
async def qa_marker(request: Request, call_next):
    """운영 자동 QA 요청 표시(학습 신호를 쌓지 않게). 토큰이 맞을 때만 켜진다."""
    from app import qa

    handle = qa.mark(request.headers.get("X-QA-Token"))
    try:
        return await call_next(request)
    finally:
        qa.reset(handle)


@api.exception_handler(UsageDenied)
async def usage_denied(_request: Request, exc: UsageDenied) -> JSONResponse:
    """한도에 걸림. `code` 로 프론트가 체험 시작·로그인·내일 다시 중 무엇을 권할지 고른다."""
    return JSONResponse(status_code=exc.status, content={"detail": exc.message, "code": exc.code})


@api.exception_handler(asyncio.TimeoutError)
async def action_timeout(_request: Request, _exc: asyncio.TimeoutError) -> JSONResponse:
    """외부 호출이 물려 상한을 넘긴 경우. 코스 큐는 이미 풀린 상태다."""
    return JSONResponse(
        status_code=504,
        content={"detail": "처리가 너무 오래 걸려 중단했어요. 잠시 후 다시 시도해주세요."},
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


@api.get("/health")
async def health() -> dict:
    """살아 있는지 본다(liveness). 프로세스가 응답하면 항상 200.

    컨테이너 헬스체크가 부르는 곳이라 DB·외부 연동 상태도 함께 싣는다
    (`docker inspect` 로 바로 보이도록). 판정 자체는 응답 여부로만 한다.
    """
    from app.db import is_ready

    return {
        "status": "ok",
        "db": is_ready(),
        "env": settings.env,
        # 어떤 외부 연동이 살아 있는지 — 키가 없으면 폴백으로 도는 중이다
        "integrations": {
            "kakao": bool(settings.kakao_rest_api_key),
            "naver": settings.naver_search_enabled,
            "google": bool(settings.google_maps_api_key),
            "tourapi": bool(settings.tourapi_service_key),
            "llm": bool(settings.anthropic_api_key or settings.openai_api_key),
            "sms": settings.sms_enabled,
            "payment": settings.payment_enabled,
        },
        "free_mode": settings.free_mode,
        "ai_notice": settings.ai_notice,
    }


@api.get("/health/ready")
async def readiness(response: Response) -> dict:
    """트래픽을 받을 준비가 됐는지(readiness).

    운영에서 DB 가 붙지 않았다면 인메모리로 조용히 도는 대신 503 을 내서
    로드밸런서가 이 인스턴스를 빼도록 한다. 개발에서는 상태만 알려 준다.
    """
    from app.db import is_ready

    db_ready = is_ready()
    missing = _production_warnings() if settings.is_production else []
    ok = (db_ready or not settings.is_production) and not missing
    if not ok:
        response.status_code = 503
    return {
        "status": "ok" if ok else "unavailable",
        "db": db_ready,
        "env": settings.env,
        # 값이 아니라 '비어 있다'는 사실만 노출한다
        "missing_settings": missing,
        # 결제 키가 없어도 서비스는 뜬다(기동 조건 아님). 다만 운영에서 꺼져
        # 있으면 포인트 구매가 503 이므로, 켜졌는지 여기서 볼 수 있게 한다.
        "payment_enabled": settings.payment_enabled,
    }


api.include_router(admin_router)
api.include_router(accounts_router)
api.include_router(signals_router)
api.include_router(together_router)
api.include_router(chat_router)


_AREA_CACHE: dict[str, tuple[float, dict | None]] = {}
AREA_TTL_SEC = 600


AREA_CACHE_MAX = 200


@api.get("/areas/status")
async def area_status(region: str) -> dict | None:
    """동네 혼잡도(서울 실시간 도시데이터). 키가 없거나 매핑이 없으면 null. 10분 캐시."""
    import time as _time

    import httpx

    from app.adapters.seoul_openapi import area_status as fetch

    region = region.strip()[:30]
    if not region:
        return None
    hit = _AREA_CACHE.get(region)
    if hit and _time.monotonic() - hit[0] < AREA_TTL_SEC:
        return hit[1]
    async with httpx.AsyncClient(timeout=6) as client:
        st = await fetch(client, region)
    data = (
        {"area": st.area, "level": st.level, "message": st.message, "calmer_hour": st.calmer_hour}
        if st and st.level
        else None
    )
    if len(_AREA_CACHE) >= AREA_CACHE_MAX:  # 아무 문자열로 캐시를 불리지 못하게
        _AREA_CACHE.pop(min(_AREA_CACHE, key=lambda k: _AREA_CACHE[k][0]))
    _AREA_CACHE[region] = (_time.monotonic(), data)
    return data


@api.get("/config/public")
def public_config() -> dict:
    """프론트가 런타임에 읽는 공개 설정. 비밀값은 절대 넣지 않는다(키 ID 는 원래 공개값)."""
    return {
        "naver_map_client_id": settings.naver_map_client_id or settings.ncp_api_key_id or "",
        # 로그인 수단. 카카오 client_id 는 원래 인가 주소창에 실리는 공개값이다
        "kakao_login_client_id": settings.kakao_login_client_id or None,
        "phone_login": settings.sms_enabled or not settings.is_production,
    }


@api.post("/courses", response_model=Course)
async def create_course(
    request: Request,
    x_user_id: str | None = Header(default=None),
    x_user_token: str | None = Header(default=None),
) -> Course:
    """새 코스. 체험(게스트)은 1개·IP 당 하루 1개, 회원은 하루 몫 안에서.

    신원 없이는 만들 수 없다 — 주인 없는 코스는 누구나 주인 행세를 할 수 있었다.
    """
    caller = require_caller(x_user_id, x_user_token)
    charge("course", subject=caller.user_id, guest=caller.guest, ip=client_ip(request))
    return store.create(owner_id=caller.user_id)


@api.post("/courses/{course_id}/duplicate", response_model=Course)
async def duplicate_course(
    course_id: str,
    request: Request,
    x_user_id: str | None = Header(default=None),
    x_user_token: str | None = Header(default=None),
) -> Course:
    """코스 복제. 지난 코스를 원본을 건드리지 않고 다시 편집하고 싶을 때 쓴다.

    공유받은 코스도 복제할 수 있고, 사본의 생성자는 요청자다(새 코스 몫을 쓴다).
    """
    source = store.get(course_id)
    if source is None:
        raise HTTPException(status_code=404, detail="코스를 찾을 수 없어요")
    caller = require_caller(x_user_id, x_user_token)
    charge("course", subject=caller.user_id, guest=caller.guest, ip=client_ip(request))
    copy = source.model_copy(deep=True)
    copy.id = store.new_id()
    copy.owner_id = caller.user_id
    copy.together = None  # 원본의 상대 링크·카드를 사본이 들고 가지 않게
    copy.title = f"{source.title} (사본)"
    copy.locked = False
    store.save(copy)
    return copy


@api.get("/users/{user_id}/courses", response_model=list[Course])
async def my_courses(
    user_id: str, limit: int = 50, x_user_id: str | None = Header(default=None),
    x_user_token: str | None = Header(default=None),
) -> list[Course]:
    """마이페이지: 내가 생성한 코스 히스토리 (9-4). 최근 limit 개."""
    _require_self(user_id, x_user_id, x_user_token)
    return store.list_by_owner(user_id, max(1, min(limit, 100)))


@api.get("/users/{user_id}/bookmarks", response_model=list[Course])
async def my_bookmarks(
    user_id: str, limit: int = 50, x_user_id: str | None = Header(default=None),
    x_user_token: str | None = Header(default=None),
) -> list[Course]:
    _require_self(user_id, x_user_id, x_user_token)
    ids = bookmark_store.list_course_ids(user_id, max(1, min(limit, 100)))
    return store.get_many(ids)


BOOKMARK_WEIGHT = 2  # 북마크는 채택보다 강한 관심 신호


@api.put("/users/{user_id}/bookmarks/{course_id}")
async def add_bookmark(
    user_id: str, course_id: str, x_user_id: str | None = Header(default=None),
    x_user_token: str | None = Header(default=None),
) -> dict:
    _require_self(user_id, x_user_id, x_user_token)
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
    user_id: str, x_user_id: str | None = Header(default=None),
    x_user_token: str | None = Header(default=None),
) -> dict:
    """회원 탈퇴. 계정·전화번호·내 코스·북마크를 지운다(본인만).

    개인정보 삭제 요청을 코드로 처리할 수 있게 한다. 남는 것은 개인을 식별할 수
    없는 집계 신호(장소 인기 등)뿐이다.
    """
    _require_self(user_id, x_user_id, x_user_token)
    if user_store.get(user_id) is None:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없어요")
    my_courses = store.list_by_owner(user_id, limit=1000)
    for course in my_courses:
        store.delete(course.id)
        chat_store.clear(course.id)
    bookmark_store.remove_all(user_id)
    from app.referrals import referral_store

    referral_store.forget(user_id)  # 유입 기록. 보상 기록(로그인 수단 해시)은 재가입 재보상 방지로 남는다
    user_store.delete(user_id)
    return {"ok": True, "deleted_courses": len(my_courses)}


@api.delete("/users/{user_id}/bookmarks/{course_id}")
async def remove_bookmark(
    user_id: str, course_id: str, x_user_id: str | None = Header(default=None),
    x_user_token: str | None = Header(default=None),
) -> dict:
    _require_self(user_id, x_user_id, x_user_token)
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
    course_id: str,
    req: RenameRequest,
    x_user_id: str | None = Header(default=None),
    x_user_token: str | None = Header(default=None),
) -> Course:
    """코스 이름 변경. 생성자가 있는 코스는 생성자만 변경할 수 있다."""
    course = _owned_course(course_id, x_user_id, x_user_token)
    course.title = req.title.strip()
    store.save(course)
    await broadcast_state(course_id, course.model_dump(mode="json"))
    return course


@api.delete("/courses/{course_id}")
async def delete_course(
    course_id: str,
    x_user_id: str | None = Header(default=None),
    x_user_token: str | None = Header(default=None),
) -> dict:
    """코스 삭제. 생성자가 있는 코스는 생성자만 삭제할 수 있다."""
    _owned_course(course_id, x_user_id, x_user_token)
    store.delete(course_id)
    return {"ok": True}


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


def _metered(
    feature: str, request: Request, user_id: str | None, token: str | None
):
    """비싼 조회를 한 번 쓴다. 로그인·체험 계정이면 그 사람 몫, 아니면(공유 링크로 온 상대 등)
    IP 를 체험 몫으로 센다 — 신원 없이도 쓸 수는 있게 하되 끝없이는 못 쓰게."""
    from app.usage import ip_subject

    caller = resolve_caller(user_id, token)
    if caller is not None:
        return charge(feature, subject=caller.user_id, guest=caller.guest)
    return charge(feature, subject=ip_subject(client_ip(request)), guest=True)


@api.post("/reviews/summary")
async def review_summary(
    req: ReviewSummaryRequest,
    request: Request,
    x_user_id: str | None = Header(default=None),
    x_user_token: str | None = Header(default=None),
) -> dict:
    """장소 상세 모달용 리뷰 요약 (4-2 + 8장 RAG). 같은 장소는 잠시 캐시한다.

    캐시 키는 장소만 — 질의 문구를 바꿔 가며 캐시를 비켜 유료 호출을 반복하지 못하게.
    캐시에 있으면 횟수를 세지 않는다(돈이 들지 않으니까).
    """
    cache_key = (req.place_id, "")
    cached = _summary_cache_get(cache_key)
    if cached is not None:
        return cached
    from app.places import place_repo

    # 이름은 서버가 가진 값만 쓴다 — 클라이언트가 보낸 이름으로 다른 가게 리뷰를 이 장소에 심을 수 있었다
    stored = place_repo.get_many([req.place_id]).get(req.place_id)
    if stored is None:
        return {"summary": "", "count": 0, "pros": [], "cons": []}
    ticket = _metered("review", request, x_user_id, x_user_token)
    try:
        return await _review_summary(req.place_id, stored, cache_key, ticket)
    except BaseException:
        ticket.release()  # 결과를 못 줬다
        raise


async def _review_summary(place_id: str, stored: Place, cache_key: tuple[str, str], ticket) -> dict:
    query = "분위기 방문 후기"  # 고정 — 질의를 바꿔 가며 유료 호출을 반복하지 못하게

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
        found = await retrieve(place_id, query, db_ready=db_ready)
        if not found:
            # 최초 조회 시 수집 후 재검색
            await ingest_place_reviews(place_id, stored.name, db_ready)
            found = await retrieve(place_id, query, db_ready=db_ready)
    else:
        # DB 미사용(개발): 수집+협찬 필터만 적용한 리뷰를 바로 요약
        found = await fetch_filtered(stored.name)
    summary = await summarize_reviews(found)
    pros, cons = extract_aspects(found)
    # 배치가 모아 둔 사실 태그(주차·단체석 등)를 함께 얹는다 — 리뷰 소스 키가 없어도
    # 이 정보는 쓸 수 있고, 리뷰에서 뽑은 축과 중복되면 한 번만 보여준다.
    pros = pros + [t for t in stored.fact_tags if t not in pros]
    cons = cons + [t for t in stored.caution_tags if t not in cons]
    pros = [t for t in pros if t not in cons]
    result = {"summary": summary, "count": len(found), "pros": pros, "cons": cons}
    if found:  # 빈 결과는 캐시하지 않는다(수집 전일 수 있음)
        _summary_cache_put(cache_key, result)
    else:
        ticket.release()  # 리뷰가 없었다 — 보여 준 게 없으니 몫을 돌려준다
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


def _editable(
    course_id: str, user_id: str | None, user_token: str | None, together_token: str | None
) -> Course:
    """손 편집 권한. 코스 id 는 공유 링크로 누구에게나 가므로 id 만으로는 못 고친다."""
    course = store.get(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="코스를 찾을 수 없어요")
    course_editor(course, user_id, user_token, together_token)
    return course


def _reject_duplicates(place_ids: list[str]) -> None:
    """같은 장소가 두 번 들어가면 이동시간 0 구간과 신호 왜곡이 생긴다."""
    if len(set(place_ids)) != len(place_ids):
        raise HTTPException(status_code=400, detail="같은 장소를 두 번 담을 수 없어요")


class ReorderRequest(BaseModel):
    # 원하는 최종 순서. 빠진 id 는 삭제로 처리.
    place_ids: list[str] = Field(max_length=MAX_COURSE_ITEMS)


@api.post("/courses/{course_id}/reorder", response_model=Course)
async def manual_reorder(
    course_id: str, req: ReorderRequest,
    x_user_id: str | None = Header(default=None),
    x_user_token: str | None = Header(default=None),
    x_together_token: str | None = Header(default=None),
) -> Course:
    """수동 편집(드래그/삭제). AI 미호출·무료지만 서버 큐로 직렬화 + broadcast (5-1).

    생성자(서명 토큰) 또는 같이 정하는 상대(링크 토큰)만. 크레딧 불필요.
    """
    _reject_duplicates(req.place_ids)
    _editable(course_id, x_user_id, x_user_token, x_together_token)

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
async def add_place(
    course_id: str, req: AddPlaceRequest,
    x_user_id: str | None = Header(default=None),
    x_user_token: str | None = Header(default=None),
    x_together_token: str | None = Header(default=None),
) -> Course:
    """추천("함께 가요") 장소를 코스 끝에 추가 후 전체 동선 재계산 (수동 편집).

    장소는 전역 저장소에서 복원. AI 미호출·무료. 생성자 또는 같이 정하는 상대만.
    """
    _editable(course_id, x_user_id, x_user_token, x_together_token)

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
async def set_items(
    course_id: str, req: SetItemsRequest,
    x_user_id: str | None = Header(default=None),
    x_user_token: str | None = Header(default=None),
    x_together_token: str | None = Header(default=None),
) -> Course:
    """코스 항목을 지정한 순서로 설정 후 동선 재계산 (수동 편집).

    현재 코스에 없는 id 는 전역 장소 저장소에서 복원하므로, 삭제한 장소를 되살리는
    되돌리기(undo)도 이 엔드포인트 하나로 처리된다. AI 미호출·무료. 생성자 또는 같이 정하는 상대만.
    """
    _reject_duplicates(req.place_ids)
    _editable(course_id, x_user_id, x_user_token, x_together_token)

    async def action() -> Course:
        course = store.get(course_id)
        if course is None:
            raise HTTPException(status_code=404, detail="코스를 찾을 수 없어요")
        if course.locked:
            raise HTTPException(status_code=409, detail="AI 처리 중에는 편집할 수 없습니다")

        from app.places import place_repo

        current = {it.place.id: it.place for it in course.items}
        # 대안 시트에서 고른 곳은 저장소에 없을 수 있다(실시간 검색 결과) → 현재 칸들의 대안에서 찾는다
        alt_of: dict[str, tuple[Place, list[Place]]] = {}  # 대안 id → (원래 장소, 그 칸의 대안들)
        for it in course.items:
            for a in it.alternatives:
                alt_of.setdefault(a.id, (it.place, it.alternatives))
                current.setdefault(a.id, a)
        old_alts = {it.place.id: it.alternatives for it in course.items}
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
        # 빠진 장소 = 원래 코스에 있던 칸 중 이번에 없는 것(대안은 코스에 있던 게 아니므로 제외)
        dropped = [pid for pid in old_alts if pid not in set(req.place_ids)]
        course.items = (
            await recompute(
                [p for p in places if p is not None], start, _infer_mode(course.items), get_map_service()
            )
            if places
            else []
        )
        # 대안 유지: 그대로 남은 칸은 원래 대안, 대안으로 바꾼 칸은 "원래 장소 + 나머지 대안"
        for it in course.items:
            pid = it.place.id
            if pid in old_alts:
                it.alternatives = old_alts[pid]
            elif pid in alt_of:
                orig, alts = alt_of[pid]
                it.alternatives = [orig, *[a for a in alts if a.id != pid]][:4]
        store.save(course)
        popularity_store.bump_many(dropped, weight=-1)  # 생존율(#3): 빠진 장소 상쇄
        await broadcast_state(course_id, course.model_dump(mode="json"))
        return course

    return await queues.run(course_id, action)


@api.get("/places/search", response_model=list[Place])
async def search_places(
    region: str,
    request: Request,
    q: str = "",
    limit: int = 8,
    x_user_id: str | None = Header(default=None),
    x_user_token: str | None = Header(default=None),
) -> list[Place]:
    """장소 검색 (직접 추가·교체용). 결과는 전역 저장소에 보관해 이후 id 로 복원 가능.

    region 은 필수, q 는 추가 키워드. 횟수는 사람(없으면 IP) 단위로 센다.
    """
    region = region.strip()[:30]
    q = q[:60]
    if not region:
        raise HTTPException(status_code=400, detail="지역을 입력해주세요")
    _metered("search", request, x_user_id, x_user_token)
    limit = max(1, min(limit, 20))
    keywords = [w for w in q.split() if w]
    places = await get_map_service().search_places(region, keywords, limit)
    # 학원·학교·병원 같은 데이트 부적합 업태는 직접 검색에서도 뺀다("홍대 카페"에 미술학원이 섞였다).
    # 단, 사용자가 이름을 정확히 쳐서 찾은 곳은 남긴다.
    from app.pipeline.planner import is_unfit_for_date

    places = [p for p in places if not is_unfit_for_date(p) or (q and q.strip() in p.name)]

    from app.places import place_repo

    place_repo.upsert_many(places)  # 검색 결과를 id 로 추가할 수 있게 보관
    return places


# Socket.IO 를 FastAPI 에 마운트한 ASGI 앱
app = socketio.ASGIApp(sio, other_asgi_app=api)
