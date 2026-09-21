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


def test_크론_로그가_쓸_수_있는_경로로_간다():
    """/var/log 는 root 소유로 만들어진다 — 크론은 일반 사용자로 돌기 때문에
    >> 리다이렉트가 권한 거부로 죽고 5개 잡이 전부 조용히 실행되지 않는다."""
    text = (OPS / "crontab.txt").read_text()
    assert "/var/log" not in text
    assert text.count("{{ROOT}}/logs/") == 5


def test_설치_스크립트가_로그_백업_디렉터리를_만들고_쓰기를_확인한다():
    text = (OPS / "install_cron.sh").read_text()
    assert 'mkdir -p "$ROOT/logs" "$ROOT/backups"' in text
    assert "sudo mkdir -p /var/log" not in text
    assert "-w" in text  # 쓰기 가능 여부를 실제로 검사한다


def test_백업_기본_경로가_저장소_아래다():
    assert 'BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"' in (OPS / "backup.sh").read_text()


def test_deploy_가_env_의_위험한_값을_경고한다(tmp_path):
    """deploy.sh 는 .env 를 bash 로 읽는다 — 따옴표 없는 공백·#·$ 는 값을 망가뜨린다."""
    import shutil

    work = tmp_path / "repo"
    work.mkdir()
    shutil.copy(ROOT / "deploy.sh", work / "deploy.sh")
    (work / ".env").write_text(
        "DOMAIN=example.com\n"
        "POSTGRES_PASSWORD=abc def\n"   # 공백 → 잘린다
        "ADMIN_TOKEN=tok#en\n"          # # → 주석으로 먹힌다
        "SESSION_SECRET='ok value'\n"   # 따옴표로 감쌌으면 괜찮다
    )
    # 경고 로직만 떼어 실행한다(전체 배포는 도커가 필요하다)
    script = (ROOT / "deploy.sh").read_text()
    start = script.index('risky="$(grep')
    end = script.index("fi\n", start) + 3
    proc = subprocess.run(
        ["bash", "-c", script[start:end]], cwd=work, capture_output=True, text=True
    )
    assert "POSTGRES_PASSWORD" in proc.stderr
    assert "ADMIN_TOKEN" in proc.stderr
    assert "SESSION_SECRET" not in proc.stderr


@pytest.mark.parametrize(
    "dockerfile",
    [ROOT / "backend" / "Dockerfile", ROOT / "frontend" / "Dockerfile"],
    ids=lambda p: p.parent.name,
)
def test_Dockerfile_에_줄_끝_주석이_없다(dockerfile):
    """Dockerfile 은 명령 줄 끝 주석을 지원하지 않는다.

    `FROM python:3.11 # 메모` 는 인자가 셋이 아니어서
    "FROM requires either one or three arguments" 로 빌드가 깨진다.
    이걸 못 잡아 Release images 가 14번 연속 실패했다.
    """
    bad = [
        line
        for line in dockerfile.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#") and " #" in line
    ]
    assert not bad, f"{dockerfile.parent.name}/Dockerfile 줄 끝 주석: {bad}"


def test_배치_크론이_nice_로_돈다():
    """VM 이 1 OCPU 다 — 배치가 CPU 를 잡으면 API 응답이 밀린다."""
    lines = [
        ln for ln in (OPS / "crontab.txt").read_text().splitlines()
        if re.match(r"^[\d*]", ln) and "scripts/" in ln and "ops/" not in ln
    ]
    assert len(lines) == 3  # localdata / build_places / refresh_places
    assert all("nice -n 19" in ln for ln in lines)


def test_deploy가_배치_중에는_기다린다():
    text = (ROOT / "deploy.sh").read_text()
    assert "wait_for_batch" in text
    assert "is_locked" in text
    assert "FORCE_DEPLOY" in text  # 강행 옵션
    assert "BATCH_WAIT_MIN:-30" in text  # 최대 30분
