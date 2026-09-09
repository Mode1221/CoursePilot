"""LOCALDATA CSV 내려받기 — 주 1회 갱신용.

무인증 공개 파일이라 URL 만 있으면 된다. 어떤 시군구·업종 파일을 쓸지는 운영
환경마다 다르므로 URL 목록을 설정에서 받고, 코드에는 박아 두지 않는다.
내려받기에 실패한 파일은 건너뛴다 — 한 지역이 막혀도 나머지는 갱신돼야 한다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from app.config import settings

TIMEOUT_SEC = 60  # 시군구 파일은 수십 MB 가 될 수 있다
MIN_BYTES = 100  # 이보다 작으면 오류 페이지로 본다
_NAME_RE = re.compile(r"[^0-9A-Za-z가-힣._-]")


@dataclass
class FetchReport:
    saved: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


def file_name_for(url: str, index: int) -> str:
    """URL 에서 안전한 파일명을 만든다(쿼리 문자열·경로 구분자 제거)."""
    tail = url.split("?")[0].rstrip("/").split("/")[-1]
    cleaned = _NAME_RE.sub("_", tail)
    if not cleaned.lower().endswith(".csv"):
        cleaned = f"{cleaned or 'localdata'}_{index}.csv"
    return cleaned


async def fetch_all(
    urls: list[str] | None = None, target_dir: str | None = None
) -> FetchReport:
    """설정된 URL 들을 내려받아 CSV 디렉터리에 저장한다."""
    urls = urls if urls is not None else list(settings.localdata_csv_urls)
    directory = target_dir or settings.localdata_csv_dir
    report = FetchReport()
    if not urls or not directory:
        return report
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=TIMEOUT_SEC, follow_redirects=True) as client:
        for index, url in enumerate(urls):
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                if len(resp.content) < MIN_BYTES:
                    raise ValueError("응답이 너무 짧다(오류 페이지로 보임)")
                (path / file_name_for(url, index)).write_bytes(resp.content)
            except Exception:
                report.failed.append(url)
                continue
            report.saved.append(url)
    if report.saved:
        # 새 파일을 받았으면 다음 조회부터 다시 읽도록 캐시를 비운다.
        from app.adapters.localdata import get_localdata_registry

        get_localdata_registry().clear()
    return report
