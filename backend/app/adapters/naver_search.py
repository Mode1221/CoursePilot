"""네이버 검색(지역·블로그) 엔드포인트 선택 — NAVER API HUB 우선, 개발자센터는 레거시.

2026-07-31 부로 네이버 개발자센터의 검색 API 신규 발급이 끝났다. 신규는 네이버
클라우드 플랫폼의 NAVER API HUB 에서만 받을 수 있고, 호스트·경로·인증 헤더가 다르다.

    구(개발자센터)  https://openapi.naver.com/v1/search/local.json   X-Naver-Client-Id/Secret
    신(API HUB)     https://naverapihub.apigw.ntruss.com/search/v1/local  X-NCP-APIGW-API-KEY-ID/KEY

요청 파라미터(query·display·start·sort)와 응답(items·total·mapx·mapy)은 같다.
개발자센터 키는 2027-06-30 에 전면 종료되므로, 둘 다 있으면 API HUB 를 쓴다.
"""
from __future__ import annotations

from app.config import settings

APIHUB_BASE = "https://naverapihub.apigw.ntruss.com/search/v1"
LEGACY_BASE = "https://openapi.naver.com/v1/search"

_KINDS = ("local", "blog")


def search_endpoint(kind: str) -> tuple[str, dict[str, str]] | None:
    """kind('local'|'blog') 의 (URL, 인증 헤더). 키가 없으면 None.

    호출부는 None 이면 검색을 건너뛴다(폴백). URL 은 그대로 GET 하면 되고,
    파라미터는 두 방식이 같다.
    """
    if kind not in _KINDS:
        raise ValueError(f"unknown naver search kind: {kind}")
    if settings.naver_apihub_key_id and settings.naver_apihub_key:
        return (
            f"{APIHUB_BASE}/{kind}",
            {
                "X-NCP-APIGW-API-KEY-ID": settings.naver_apihub_key_id,
                "X-NCP-APIGW-API-KEY": settings.naver_apihub_key,
            },
        )
    if settings.naver_client_id:
        return (
            f"{LEGACY_BASE}/{kind}.json",
            {
                "X-Naver-Client-Id": settings.naver_client_id,
                "X-Naver-Client-Secret": settings.naver_client_secret,
            },
        )
    return None


def is_apihub() -> bool:
    """현재 API HUB 키로 도는지(스모크·헬스 표시용)."""
    return bool(settings.naver_apihub_key_id and settings.naver_apihub_key)
