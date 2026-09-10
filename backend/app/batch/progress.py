"""배치 진행 상태 저장 — 중간에 죽어도 이어서 한다.

상권 24곳 × 카테고리 4종 = 96회 수집을 도중에 잃으면(네트워크 오류·rate limit·
프로세스 종료) 재실행이 처음부터 다시 돈다. 끝낸 조각을 남겨 두고, 재실행 때
남은 것부터 이어 가게 한다.

파일 하나에 JSON 으로 적는다 — 배치는 VM 한 대에서 도는 단일 프로세스이고,
DB 가 아직 안 붙은 상태(첫 구축)에서도 동작해야 한다.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

# 이 시간이 지난 진행 상태는 새 실행으로 본다(어제 것을 이어받지 않는다).
STALE_AFTER_HOURS = 20
DEFAULT_PATH = Path(os.environ.get("BATCH_STATE_DIR", "/tmp")) / "coursepilot_places_build.json"


class Progress:
    """끝낸 (상권, 카테고리) 조각을 기록한다."""

    def __init__(self, path: Path | str | None = None, *, now: datetime | None = None) -> None:
        self.path = Path(path) if path else DEFAULT_PATH
        self._now = now or datetime.now(UTC)
        self.done: set[str] = set()
        self.resumed = False
        self._load()

    # --- 저장·복원 ----------------------------------------------------
    def _load(self) -> None:
        try:
            raw = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return
        started = raw.get("started_at")
        try:
            when = datetime.fromisoformat(started) if started else None
        except ValueError:
            when = None
        if when is None or self._now - when > timedelta(hours=STALE_AFTER_HOURS):
            return  # 오래된 상태는 버린다(어제 배치의 잔여물)
        self.done = set(raw.get("done") or [])
        self.started_at = when
        self.resumed = bool(self.done)

    def _save(self) -> None:
        payload = {
            "started_at": getattr(self, "started_at", self._now).isoformat(),
            "done": sorted(self.done),
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # 쓰다가 죽어도 반쪽 파일이 남지 않게 임시 파일 → 원자적 교체
            with tempfile.NamedTemporaryFile(
                "w", dir=self.path.parent, delete=False, encoding="utf-8"
            ) as fh:
                json.dump(payload, fh, ensure_ascii=False)
                tmp = Path(fh.name)
            tmp.replace(self.path)
        except OSError:
            pass  # 상태를 못 남겨도 배치 자체는 계속한다

    # --- 사용 ---------------------------------------------------------
    @staticmethod
    def key(district: str, group_code: str) -> str:
        return f"{district}:{group_code}"

    def is_done(self, district: str, group_code: str) -> bool:
        return self.key(district, group_code) in self.done

    def mark(self, district: str, group_code: str) -> None:
        self.done.add(self.key(district, group_code))
        self._save()

    def clear(self) -> None:
        """정상 완주. 다음 실행이 처음부터 돌도록 상태를 지운다."""
        self.done.clear()
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass
