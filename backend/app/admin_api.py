"""관리 엔드포인트(/admin/*).

운영자만 보는 관측 지표라 라우팅·인증을 한곳에 모아 둔다. 개인정보 없이
집계값만 노출한다. ADMIN_TOKEN 미설정 시에는 개발 편의를 위해 열려 있다.
"""
from __future__ import annotations

import logging
import secrets

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import HTMLResponse

from app.config import settings
from app.users import user_store

admin_router = APIRouter(prefix="/admin", tags=["admin"])

@admin_router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(x_admin_token: str | None = Header(default=None)) -> str:
    """지표를 눈으로 보는 한 페이지. 데이터는 브라우저가 metrics/signals 로 다시 받는다.

    HTML 자체에는 집계값이 없으므로 토큰 검사는 데이터 엔드포인트가 맡는다
    (토큰을 화면에서 입력해 넣을 수 있어야 하기 때문).
    """
    from app.admin_dashboard import DASHBOARD_HTML

    return DASHBOARD_HTML


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


@admin_router.get("/together")
async def admin_together(days: int = 90, x_admin_token: str | None = Header(default=None)) -> dict:
    """합의 코스 퍼널·합의 시간·역할 역전·30일 재사용(실험 지표). 개인정보 없음."""
    _require_admin(x_admin_token)
    from datetime import datetime, timedelta

    from app.funnel import funnel_store, summarize

    return summarize(funnel_store.events(since=datetime.now() - timedelta(days=days)))


@admin_router.get("/growth")
async def admin_growth(x_admin_token: str | None = Header(default=None)) -> dict:
    """유입·초대: 최근 7·30일 체험·가입의 첫 방문 출처별 수, 보낸 초대(같이 정하기 링크),
    초대로 온 가입, 준 초대 보상. 운영 자동 QA 는 처음부터 기록하지 않는다. 개인정보 없음."""
    _require_admin(x_admin_token)
    from app.referrals import INVITE_REWARD_CAP, INVITE_REWARD_WINDOW_DAYS, growth_stats
    from app.usage import INVITE_BONUS, INVITE_BONUS_DAYS

    return {
        "windows": growth_stats(),
        "reward_rule": {
            "bonus_per_day": INVITE_BONUS,
            "days": INVITE_BONUS_DAYS,
            "cap_per_inviter": INVITE_REWARD_CAP,
            "cap_window_days": INVITE_REWARD_WINDOW_DAYS,
        },
    }


@admin_router.get("/metrics")
async def admin_metrics(x_admin_token: str | None = Header(default=None)) -> dict:
    """엔드포인트별 요청 수·에러·지연(p50/p95). 인메모리, 인스턴스 단위."""
    _require_admin(x_admin_token)
    from app.metrics import metrics_store

    return metrics_store.snapshot()


@admin_router.get("/signals")
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


@admin_router.post("/qa-session")
async def qa_session(x_qa_token: str | None = Header(default=None)) -> dict:
    """운영 자동 QA 가 로그인 흐름을 돌릴 전용 회원 세션. QA_TOKEN 이 없거나 틀리면 없는 척(404).

    체험(게스트)으로 돌리면 IP 당 체험 상한에 걸리고 체험 지표를 흐린다 — 전용 회원을 쓴다.
    이 세션의 요청도 `X-QA-Token` 을 함께 보내 학습 신호를 쌓지 않는다(app/qa.py).
    """
    from app import qa
    from app.session_token import issue

    if not qa.token_ok(x_qa_token):
        raise HTTPException(status_code=404, detail="Not Found")
    user = user_store.find_by_phone(qa.QA_PHONE) or user_store.create(qa.QA_PHONE)
    return {"user_id": user.id, "token": issue(user.id), "kind": "member"}
