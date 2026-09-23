"""네이버 데이터랩 검색어 트렌드 — 가게 이름이 요즘 얼마나 검색되는지(주간).

API HUB 우선, 개발자센터 레거시 폴백(검색 API 와 같은 규칙). 한 요청에 최대 5개 그룹.
비율은 요청 안 최댓값 100 기준 상대값이라, 시계열 모양(상승·스파이크)만 쓴다.
경로는 스모크(scripts/smoke_datalab.py)로 확인한다.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

APIHUB_URL = "https://naverapihub.apigw.ntruss.com/datalab/v1/search"
LEGACY_URL = "https://openapi.naver.com/v1/datalab/search"
MAX_GROUPS = 5
WEEKS = 16


def endpoint() -> tuple[str, dict[str, str]] | None:
    if settings.naver_apihub_key_id and settings.naver_apihub_key:
        return APIHUB_URL, {
            "X-NCP-APIGW-API-KEY-ID": settings.naver_apihub_key_id,
            "X-NCP-APIGW-API-KEY": settings.naver_apihub_key,
            "Content-Type": "application/json",
        }
    if settings.naver_client_id:
        return LEGACY_URL, {
            "X-Naver-Client-Id": settings.naver_client_id,
            "X-Naver-Client-Secret": settings.naver_client_secret,
            "Content-Type": "application/json",
        }
    return None


async def weekly_trends(
    client: httpx.AsyncClient, names: list[str], today: date | None = None
) -> dict[str, list[float]]:
    """이름 → 주간 비율(오래된 → 최근). 실패·결과 없음은 빈 목록."""
    ep = endpoint()
    if ep is None or not names:
        return {}
    url, headers = ep
    today = today or date.today()
    body = {
        "startDate": (today - timedelta(weeks=WEEKS)).isoformat(),
        "endDate": today.isoformat(),
        "timeUnit": "week",
        "keywordGroups": [{"groupName": n[:50], "keywords": [n[:50]]} for n in names[:MAX_GROUPS]],
    }
    try:
        resp = await client.post(url, json=body, headers=headers)
        resp.raise_for_status()
        results = resp.json().get("results") or []
    except Exception as exc:
        logger.warning("datalab 실패: %s", exc)
        return {}
    out: dict[str, list[float]] = {}
    for r in results:
        out[r.get("title", "")] = [float(d.get("ratio", 0)) for d in (r.get("data") or [])]
    return out
