"""네이버 검색 창구 선택 — API HUB(신규) 우선, 개발자센터(레거시) 폴백."""
from app.adapters.naver_search import APIHUB_BASE, LEGACY_BASE, is_apihub, search_endpoint
from app.config import settings


def test_API_HUB_키가_있으면_HUB_호스트와_NCP_헤더(monkeypatch):
    monkeypatch.setattr(settings, "naver_apihub_key_id", "hub-id")
    monkeypatch.setattr(settings, "naver_apihub_key", "hub-secret")
    monkeypatch.setattr(settings, "naver_client_id", "legacy-id")
    url, headers = search_endpoint("local")
    assert url == f"{APIHUB_BASE}/local"
    assert headers == {"X-NCP-APIGW-API-KEY-ID": "hub-id", "X-NCP-APIGW-API-KEY": "hub-secret"}
    assert is_apihub() and settings.naver_search_enabled


def test_HUB_키가_없으면_레거시(monkeypatch):
    monkeypatch.setattr(settings, "naver_apihub_key_id", "")
    monkeypatch.setattr(settings, "naver_apihub_key", "")
    monkeypatch.setattr(settings, "naver_client_id", "legacy-id")
    monkeypatch.setattr(settings, "naver_client_secret", "legacy-secret")
    url, headers = search_endpoint("blog")
    assert url == f"{LEGACY_BASE}/blog.json"
    assert headers["X-Naver-Client-Id"] == "legacy-id"
    assert not is_apihub() and settings.naver_search_enabled


def test_둘_다_없으면_None(monkeypatch):
    for name in ("naver_apihub_key_id", "naver_apihub_key", "naver_client_id", "naver_client_secret"):
        monkeypatch.setattr(settings, name, "")
    assert search_endpoint("local") is None
    assert not settings.naver_search_enabled


def test_HUB_키가_반쪽이면_레거시로(monkeypatch):
    monkeypatch.setattr(settings, "naver_apihub_key_id", "hub-id")
    monkeypatch.setattr(settings, "naver_apihub_key", "")
    monkeypatch.setattr(settings, "naver_client_id", "legacy-id")
    url, _ = search_endpoint("local")
    assert url.startswith(LEGACY_BASE)


def test_모르는_종류는_거부():
    import pytest

    with pytest.raises(ValueError):
        search_endpoint("news")
