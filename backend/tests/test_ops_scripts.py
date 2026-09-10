"""운영 스크립트가 문법·구성 면에서 성한지.

새벽 크론이 처음 도는 순간에 오타를 발견하면 늦다. 문법과 크론 항목 형식,
그리고 각 스크립트가 알림 경로를 실제로 부르는지는 미리 고정해 둔다.
"""
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
OPS = ROOT / "scripts" / "ops"
SHELL_SCRIPTS = sorted(ROOT.glob("scripts/**/*.sh")) + [ROOT / "deploy.sh"]


@pytest.mark.parametrize("script", SHELL_SCRIPTS, ids=lambda p: p.name)
def test_셸_문법이_성하다(script):
    proc = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


@pytest.mark.parametrize("script", sorted(OPS.glob("*.sh")), ids=lambda p: p.name)
def test_실행_권한이_있다(script):
    assert script.stat().st_mode & 0o111, f"{script.name} 에 실행 권한이 없다"


def test_크론_항목이_다섯_가지_작업을_덮는다():
    text = (OPS / "crontab.txt").read_text()
    jobs = [ln for ln in text.splitlines() if re.match(r"^[\d*]", ln)]
    assert len(jobs) == 5
    joined = "\n".join(jobs)
    for expected in (
        "fetch_localdata.py", "build_places.py", "refresh_places.py",
        "backup.sh", "disk_check.sh",
    ):
        assert expected in joined, f"크론에 {expected} 항목이 없다"


def test_크론_시각이_요청한_대로다():
    text = (OPS / "crontab.txt").read_text()
    assert re.search(r"^0 2 \* \* 1 .*fetch_localdata", text, re.M)   # 월 02:00
    assert re.search(r"^0 3 \* \* \* .*build_places", text, re.M)      # 매일 03:00
    assert re.search(r"^30 4 \* \* \* .*refresh_places", text, re.M)   # 매일 04:30
    assert re.search(r"^0 5 \* \* \* .*backup\.sh", text, re.M)        # 매일 05:00


def test_크론_경로는_설치_시_치환된다():
    text = (OPS / "crontab.txt").read_text()
    assert "{{ROOT}}" in text
    assert "/srv/" not in text  # 특정 경로를 박아 두지 않는다


def test_백업은_실패를_알린다():
    """조용히 실패하면 '백업이 있는 줄 알았는데 없는' 상태가 된다."""
    text = (OPS / "backup.sh").read_text()
    assert "notify.sh" in text
    assert "PIPESTATUS" in text  # pg_dump 실패를 gzip 성공에 가리지 않는다
    assert "KEEP_DAYS" in text


def test_디스크_점검은_임계를_설정으로_받는다():
    text = (OPS / "disk_check.sh").read_text()
    assert "DISK_ALERT_PERCENT" in text and "85" in text
    assert "notify.sh" in text


def test_디스크_점검이_실제로_돈다():
    proc = subprocess.run(
        ["bash", str(OPS / "disk_check.sh")],
        capture_output=True, text=True, cwd=ROOT,
        env={"PATH": "/usr/local/bin:/usr/bin:/bin", "DISK_ALERT_PERCENT": "99"},
    )
    assert proc.returncode == 0, proc.stderr
    assert "디스크" in proc.stdout


def test_알림은_웹훅이_없어도_죽지_않는다():
    proc = subprocess.run(
        ["bash", str(OPS / "notify.sh"), "테스트"],
        capture_output=True, text=True,
        env={"PATH": "/usr/local/bin:/usr/bin:/bin"},
    )
    assert proc.returncode == 0
    assert "웹훅 미설정" in proc.stdout
