"""스모크 스크립트가 키 없이도 깨지지 않는지.

키는 하나씩 들어온다. 아직 없는 벤더의 스크립트가 임포트 에러로 죽으면,
정작 키가 생겼을 때 검증을 못 한다 — 스킵 경로를 상시 지켜 둔다.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
VENDORS = ("kakao", "naver", "google", "tourapi", "kopis", "localdata")
# 키가 있는 개발 환경에서도 스킵 경로를 보도록 전부 비운다
_BLANK = {
    "KAKAO_REST_API_KEY": "", "NAVER_CLIENT_ID": "", "NAVER_CLIENT_SECRET": "",
    "GOOGLE_MAPS_API_KEY": "", "TOURAPI_SERVICE_KEY": "",
    "LOCALDATA_CSV_DIR": "", "LOCALDATA_CSV_URLS": "[]",
}


def _run(args: list[str]) -> subprocess.CompletedProcess:
    env = {**os.environ, **_BLANK}
    return subprocess.run(
        [sys.executable, *args], capture_output=True, text=True, env=env, timeout=120
    )


@pytest.mark.parametrize("vendor", VENDORS)
def test_키가_없으면_스킵으로_정상_종료한다(vendor):
    proc = _run([str(SCRIPTS / f"smoke_{vendor}.py")])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "SKIP" in proc.stdout


def test_묶음_실행도_전부_스킵이면_성공이다():
    proc = _run([str(SCRIPTS / "smoke_all.py")])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "실패 없음" in proc.stdout


def test_모르는_벤더는_거부한다():
    proc = _run([str(SCRIPTS / "smoke_all.py"), "없는벤더"])
    assert proc.returncode == 2
