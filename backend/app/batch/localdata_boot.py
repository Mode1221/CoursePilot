"""배치·검증 스크립트 진입점의 LOCALDATA 적재.

API 프로세스는 lifespan 이 백그라운드로 적재하지만, `docker compose exec` 로 뜨는
배치 스크립트는 그 lifespan 이 없다. 여기서 동기 적재하고 결과를 첫 로그로 남긴다.
"""

from __future__ import annotations

import logging
import sys
import time

from app.config import settings

logger = logging.getLogger("coursepilot")


def load_localdata_or_exit(allow_missing: bool = False) -> bool:
    """대장을 적재한다. 설정돼 있는데 비어 있으면 False(호출부가 종료).

    - LOCALDATA_CSV_DIR 미설정: 경고만 남기고 True(개발 환경).
    - 설정됐고 적재 성공: 행 수·소요를 로그로 남기고 True.
    - 설정됐는데 0건: 폐업 필터 없이 저장하면 닫힌 가게가 DB 에 들어간다 →
      allow_missing 이 아니면 False.
    """
    from app.adapters.localdata import ensure_loaded_for_batch, get_localdata_registry

    if not settings.localdata_csv_dir:
        logger.warning("LOCALDATA_CSV_DIR 미설정 — 폐업 필터 없이 진행한다")
        return True
    started = time.monotonic()
    count = ensure_loaded_for_batch()
    registry = get_localdata_registry()
    if registry.loaded:
        logger.info(
            "LOCALDATA 적재 완료 — 인덱싱 %d행, %.1f초 (%s)",
            count,
            time.monotonic() - started,
            settings.localdata_csv_dir,
        )
        return True
    msg = (
        f"LOCALDATA_CSV_DIR={settings.localdata_csv_dir} 에 적재할 CSV 가 없습니다. "
        "scripts/fetch_localdata.py 를 먼저 돌리거나 --allow-no-localdata 로 강제하세요."
    )
    if allow_missing:
        logger.warning(msg)
        return True
    print(msg, file=sys.stderr)
    return False
