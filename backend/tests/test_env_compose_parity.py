"""backend/.env.example 의 키가 prod compose 에 빠짐없이 전달되는지.

컨테이너는 compose 의 environment 에 적힌 것만 본다. .env 에 키를 넣어도
여기에 없으면 백엔드는 키가 없는 것으로 동작한다 — 조용히 폴백으로 떨어진다.
"""
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
ENV_EXAMPLE = ROOT / "backend" / ".env.example"
COMPOSE = ROOT / "docker-compose.prod.yml"
ENV_PROD = ROOT / ".env.prod.example"

# 백엔드 컨테이너가 쓰지 않는 키(프론트 빌드 시 주입).
FRONTEND_ONLY = {"NEXT_PUBLIC_NAVER_MAP_CLIENT_ID"}

_KEY_RE = re.compile(r"^([A-Z][A-Z0-9_]*)=", re.MULTILINE)


def _keys(path: Path) -> set[str]:
    return set(_KEY_RE.findall(path.read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def backend_env() -> dict:
    data = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    return data["services"]["backend"]["environment"]


def test_env_example_의_모든_키가_compose_에_있다(backend_env):
    missing = _keys(ENV_EXAMPLE) - FRONTEND_ONLY - set(backend_env)
    assert not missing, f"docker-compose.prod.yml backend.environment 에 누락: {sorted(missing)}"


def test_compose_에만_있는_키는_env_example_에도_적는다(backend_env):
    # 문서화되지 않은 설정이 생기면 운영자가 알 길이 없다.
    extra = set(backend_env) - _keys(ENV_EXAMPLE)
    assert not extra, f"backend/.env.example 에 설명이 없는 키: {sorted(extra)}"


def test_운영_예시에_키_발급_대상이_모두_적혀_있다():
    keys = _keys(ENV_PROD)
    for name in (
        "KAKAO_REST_API_KEY",
        "NAVER_CLIENT_ID",
        "NCP_API_KEY_ID",
        "TOURAPI_SERVICE_KEY",
        "GOOGLE_MAPS_API_KEY",
        "LOCALDATA_CSV_DIR",
        "LOCALDATA_HOST_DIR",
        "TRUSTED_PROXIES",
    ):
        assert name in keys, f".env.prod.example 에 {name} 가 없다"


def test_LOCALDATA_볼륨이_마운트돼_있다():
    data = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    volumes = data["services"]["backend"].get("volumes") or []
    assert any(":/data/localdata" in v for v in volumes), "LOCALDATA CSV 볼륨이 없다"


def test_신뢰_프록시_기본값이_도커_브리지_대역을_덮는다(backend_env):
    # caddy 컨테이너는 172.x 에서 온다. 못 믿으면 모든 요청이 한 IP 로 보여
    # rate limit 이 사용자별이 아니라 전역이 된다.
    assert "172.16.0.0/12" in backend_env["TRUSTED_PROXIES"]
