""".env.example 이 실제로 코드가 읽는 환경변수와 어긋나지 않게 지킨다.

설정을 추가하고 예시 파일을 잊으면, 배포하는 사람은 그 값이 있는 줄도 모른다.
"""
import re
from pathlib import Path

from app.config import Settings

ENV_EXAMPLE = Path(__file__).resolve().parents[1] / ".env.example"
# 백엔드 설정이 아니라 프론트 빌드 인자로 넘어가는 값(같은 .env 에 적어 둔다)
FRONTEND_ONLY = {"NEXT_PUBLIC_NAVER_MAP_CLIENT_ID"}


def _documented() -> set[str]:
    return set(re.findall(r"^([A-Z][A-Z0-9_]*)=", ENV_EXAMPLE.read_text(), re.M))


def test_모든_설정이_예시에_있다():
    missing = {f.upper() for f in Settings.model_fields} - _documented()
    assert not missing, f".env.example 에 빠진 설정: {sorted(missing)}"


def test_예시에_없는_설정을_적어_두지_않는다():
    extra = _documented() - {f.upper() for f in Settings.model_fields} - FRONTEND_ONLY
    assert not extra, f"코드가 읽지 않는 항목: {sorted(extra)}"


def test_각_항목에_설명이_붙어_있다():
    """값만 있고 설명이 없으면 배포자가 필수인지 선택인지 알 수 없다."""
    lines = ENV_EXAMPLE.read_text().splitlines()
    undocumented = []
    for i, line in enumerate(lines):
        m = re.match(r"^([A-Z][A-Z0-9_]*)=", line)
        if not m:
            continue
        # 위로 올라가며 주석을 찾는다. NAVER_CLIENT_ID/SECRET 처럼 한 주석이
        # 연속된 여러 변수를 함께 설명하는 경우도 문서화된 것으로 본다.
        j = i - 1
        while j >= 0 and re.match(r"^[A-Z][A-Z0-9_]*=", lines[j]):
            j -= 1
        if j < 0 or not lines[j].startswith("#"):
            undocumented.append(m.group(1))
    assert not undocumented, f"설명 주석이 없는 항목: {undocumented}"
