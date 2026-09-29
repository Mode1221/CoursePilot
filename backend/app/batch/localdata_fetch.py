"""LOCALDATA CSV 내려받기 — 주 1회 갱신용.

원천은 2026-04-16 로 localdata.go.kr 이 닫히면서 file.localdata.go.kr 로 이관됐다.
무인증 공개 파일이지만 **브라우저 User-Agent 와 Referer 가 없으면 403** 이고,
응답 헤더가 charset=UTF-8 이라 해도 실제 본문은 CP949 다(여기서는 바이트 그대로
저장하고 디코딩은 어댑터가 한다).

파일이 수백 MB(휴게음식점 약 208MB) 라 VM(6GB) 메모리에 통째로 올리지 않는다.
임시파일로 스트리밍한 뒤 원자적으로 교체하며, 실패한 파일은 건너뛴다 —
한 업종이 막혀도 나머지는 갱신돼야 한다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from app.config import settings

TIMEOUT_SEC = 600  # 200MB 대 파일이라 넉넉히(연결은 30초)
CHUNK_BYTES = 1 << 20  # 1MB 씩 흘려 쓴다
MIN_BYTES = 100  # 이보다 작으면 오류 페이지로 본다
_NAME_RE = re.compile(r"[^0-9A-Za-z가-힣._-]")

# file.localdata.go.kr 고정 다운로드 URL(날짜·토큰 없음).
DEFAULT_CSV_URLS = (
    "https://file.localdata.go.kr/file/download/general_restaurants/info",  # 일반음식점
    "https://file.localdata.go.kr/file/download/rest_cafes/info",  # 휴게음식점
)

# 헤더 없이 요청하면 403 이 떨어진다.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


@dataclass
class FetchReport:
    saved: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)


def referer_for(url: str) -> str:
    """다운로드 URL 에 대응하는 안내 페이지를 Referer 로 쓴다.

    .../file/download/<slug>/info → .../file/<slug>/info
    """
    return url.replace("/file/download/", "/file/", 1)


def headers_for(url: str) -> dict[str, str]:
    return {
        "User-Agent": USER_AGENT,
        "Referer": referer_for(url),
        "Accept": "text/csv,application/octet-stream,*/*",
    }


def file_name_for(url: str, index: int) -> str:
    """URL 에서 안전한 파일명을 만든다(쿼리 문자열·경로 구분자 제거).

    새 원천은 .../download/<slug>/info 꼴이라 마지막 토큰이 전부 "info" 다.
    그래서 슬러그를 먼저 본다.
    """
    parts = [p for p in url.split("?")[0].rstrip("/").split("/") if p]
    tail = parts[-1] if parts else ""
    if tail == "info" and len(parts) >= 2:  # .../download/<slug>/info → <slug>
        return f"{_NAME_RE.sub('_', parts[-2])}.csv"
    cleaned = _NAME_RE.sub("_", tail)
    if not cleaned.lower().endswith(".csv"):
        cleaned = f"{cleaned or 'localdata'}_{index}.csv"
    return cleaned


def _record(ok: bool) -> None:
    from app.metrics import metrics_store

    metrics_store.record_external("localdata.fetch", ok=ok)


def _check_content_type(resp: httpx.Response) -> None:
    """HTML 이 오면 점검 안내 페이지/차단이다 — CSV 로 착각해 저장하면 안 된다."""
    ctype = (resp.headers.get("content-type") or "").lower()
    if "html" in ctype:
        raise ValueError(
            f"CSV 가 아니라 HTML 이 왔다(content-type={ctype!r}). "
            "차단(User-Agent/Referer) 이거나 원천 점검 중일 수 있다."
        )


async def _download_one(client: httpx.AsyncClient, url: str, dest: Path) -> None:
    """스트리밍으로 임시파일에 받은 뒤 원자적으로 교체한다."""
    tmp = dest.with_suffix(dest.suffix + ".part")
    size = 0
    try:
        async with client.stream("GET", url, headers=headers_for(url)) as resp:
            resp.raise_for_status()
            _check_content_type(resp)
            with tmp.open("wb") as fh:
                async for chunk in resp.aiter_bytes(CHUNK_BYTES):
                    fh.write(chunk)
                    size += len(chunk)
        if size < MIN_BYTES:
            raise ValueError(f"응답이 너무 짧다({size}바이트, 오류 페이지로 보임)")
        tmp.replace(dest)  # 같은 파일시스템이라 원자적
    finally:
        tmp.unlink(missing_ok=True)


async def fetch_all(
    urls: list[str] | None = None, target_dir: str | None = None
) -> FetchReport:
    """설정된 URL 들을 내려받아 CSV 디렉터리에 저장한다."""
    if urls is None:
        urls = list(settings.localdata_csv_urls) or list(DEFAULT_CSV_URLS)
    directory = target_dir or settings.localdata_csv_dir
    report = FetchReport()
    if not urls or not directory:
        return report
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    timeout = httpx.Timeout(TIMEOUT_SEC, connect=30.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        for index, url in enumerate(urls):
            try:
                await _download_one(client, url, path / file_name_for(url, index))
            except Exception as exc:  # 한 업종이 막혀도 나머지는 계속
                _record(ok=False)
                report.failed.append(url)
                report.errors[url] = f"{type(exc).__name__}: {exc}"
                continue
            _record(ok=True)
            report.saved.append(url)
    if report.saved:
        # 새 파일을 받았으면 다음 조회부터 다시 읽도록 캐시를 비운다.
        from app.adapters.localdata import get_localdata_registry

        get_localdata_registry().clear()
    return report
