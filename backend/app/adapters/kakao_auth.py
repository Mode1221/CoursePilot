"""카카오 로그인(OAuth 2.0 인가 코드) — 인가 코드를 카카오 회원번호로 바꾼다.

흐름: 브라우저가 카카오 인가 화면 → `<사이트>/auth/kakao?code=…` 로 돌아옴 → 프론트가 code 를
백엔드로 보냄 → 여기서 토큰 교환 + 회원번호 조회. 카카오 액세스 토큰은 저장하지 않는다
(우리는 "누구인지"만 필요하고, 카카오 API 를 대신 부를 일이 없다).

공식 문서: https://developers.kakao.com/docs/latest/ko/kakaologin/rest-api
"""
from __future__ import annotations

import httpx

from app.config import settings

TOKEN_URL = "https://kauth.kakao.com/oauth/token"
ME_URL = "https://kapi.kakao.com/v2/user/me"
AUTHORIZE_URL = "https://kauth.kakao.com/oauth/authorize"


class KakaoLoginError(Exception):
    """코드가 틀렸거나 만료됐거나, 카카오가 응답하지 않았다."""


def enabled() -> bool:
    return bool(settings.kakao_login_client_id)


async def kakao_user_id(code: str, redirect_uri: str, client: httpx.AsyncClient | None = None) -> str:
    """인가 코드 → 카카오 회원번호(문자열). 실패하면 KakaoLoginError."""
    own = client is None
    http = client or httpx.AsyncClient(timeout=8)
    try:
        data = {
            "grant_type": "authorization_code",
            "client_id": settings.kakao_login_client_id,
            "redirect_uri": redirect_uri,
            "code": code,
        }
        if settings.kakao_login_client_secret:
            data["client_secret"] = settings.kakao_login_client_secret
        tok = await http.post(TOKEN_URL, data=data)
        if tok.status_code != 200:
            raise KakaoLoginError(f"token {tok.status_code}")
        access = tok.json().get("access_token")
        if not access:
            raise KakaoLoginError("no access_token")
        me = await http.get(ME_URL, headers={"Authorization": f"Bearer {access}"})
        if me.status_code != 200:
            raise KakaoLoginError(f"me {me.status_code}")
        kid = me.json().get("id")
        if kid is None:
            raise KakaoLoginError("no id")
        return str(kid)
    except httpx.HTTPError as exc:
        raise KakaoLoginError("network") from exc
    finally:
        if own:
            await http.aclose()
