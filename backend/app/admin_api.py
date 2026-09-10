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
