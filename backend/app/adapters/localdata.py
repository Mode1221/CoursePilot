"""LOCALDATA(지방행정 인허가 데이터) 어댑터 — 폐업 필터 + 업력 산출.

무료·무인증 CSV(시군구 단위)를 주 1회 내려받아 메모리 인덱스로 올린다.
용도는 두 가지뿐이다.
  1) 폐업/말소된 장소를 후보에서 제거 (검색 API 는 폐업을 걸러주지 않는다)
  2) 인허가일자로 업력(영업 년수) 산출 → 스코어링 신호

크롤링·평점 등 다른 목적에는 쓰지 않는다. 데이터가 없으면 전부 무영향(폴백).
"""
from __future__ import annotations

import csv
import logging
import re
import time
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

from app.batch.districts import DISTRICTS
from app.config import settings

logger = logging.getLogger(__name__)

RELOAD_INTERVAL_DAYS = 7  # 갱신 주기(주 1회)
SNIFF_BYTES = 4096  # 인코딩 판별에 쓰는 앞부분 크기
KEEP_RATIO_WARN = 0.05  # 인덱싱 비율이 이보다 높으면 필터가 안 먹은 것이다

# 신원천은 **업종별 전국 파일**이다(일반음식점은 200만 행이 넘는다). 전부
# 인덱싱하면 6GB VM 에서 백엔드가 OOM 으로 죽는다. 우리가 추천하는 24개 상권의
# (시도, 시군구) 행만 남긴다 — 나머지는 폐업 판정에 쓸 일이 없다.
#
# 시군구 이름만 보면 안 된다: "중구"는 부산·대구·인천·대전에도 있어서
# 전국 파일에서 엉뚱한 지역이 대량으로 딸려 들어온다.
TARGET_AREAS: frozenset[tuple[str, str]] = frozenset(
    (d.sido, d.sigungu) for d in DISTRICTS if d.sigungu
)
TARGET_SIGUNGU: frozenset[str] = frozenset(sigungu for _, sigungu in TARGET_AREAS)


def _sido_aliases(sido: str) -> tuple[str, ...]:
    """주소 표기가 제각각이다: "서울특별시"/"서울", "경기도"/"경기"."""
    short = sido
    for suffix in ("특별자치도", "특별자치시", "광역시", "특별시", "도"):
        if sido.endswith(suffix):
            short = sido[: -len(suffix)]
            break
    return (sido, short) if short != sido else (sido,)


_AREA_MATCHERS: tuple[tuple[tuple[str, ...], str], ...] = tuple(
    (_sido_aliases(sido), sigungu) for sido, sigungu in sorted(TARGET_AREAS)
)

# LOCALDATA 표준 컬럼명. 파일마다 일부만 존재할 수 있어 후보 목록으로 둔다.
_NAME_COLS = ("사업장명", "업소명", "상호명")
# 신원천(file.localdata.go.kr) 헤더는 "도로명주소"/"지번주소" 다. 구원천의
# "도로명전체주소"/"소재지전체주소" 도 남겨 둔다(예전에 받아 둔 파일 호환).
_ADDR_COLS = (
    "도로명전체주소",
    "소재지전체주소",
    "도로명주소",
    "소재지주소",
    "지번주소",
)
_STATUS_COLS = ("상세영업상태명", "영업상태명")
_OPENED_COLS = ("인허가일자", "인허가일")
_CLOSED_COLS = ("폐업일자", "폐업일")

# 폐업 판정 기준(우선순위):
#   1) 폐업일자(폐업일)가 채워져 있으면 폐업
#   2) 아니면 상세영업상태명 → 영업상태명 에 아래 낱말이 들어가면 영업하지 않음
# "영업/정상" 이 정상 영업 값이고, 그 밖의 값(폐업, 휴업, 취소, 말소 등)은 코스에
# 넣지 않는다. 휴업도 제외한다 — 당장 갈 수 없는 곳을 추천하면 안 된다.
# 실제 분포는 `python scripts/localdata_status_dist.py` 로 확인한다.
_CLOSED_STATUSES = (
    "폐업",
    "말소",
    "취소",
    "직권말소",
    "폐쇄",
    "허가취소",
    "휴업",
)

_NAME_NOISE_RE = re.compile(r"[\s()（）\[\]·.\-_'\"]+")
_ADDR_NUM_RE = re.compile(r"\d+")


def _norm_name(name: str) -> str:
    """공백·기호를 털어낸 상호 비교 키."""
    return _NAME_NOISE_RE.sub("", name or "").lower()


def _name_keys(name: str) -> list[str]:
    """지점 접미사("…성수점")를 떼어낸 변형까지 포함한 비교 키들.

    접미사 길이를 모르므로 2~4자를 잘라본 변형을 모두 키로 쓴다. 남는 몸통이
    두 글자 미만이면 다른 상호와 충돌하므로 버린다.
    """
    base = _norm_name(name)
    keys = [base]
    if base.endswith("점"):
        for cut in (2, 3, 4):
            trimmed = base[:-cut]
            if len(trimmed) >= 2:
                keys.append(trimmed)
    return keys


def _addr_tokens(address: str | None) -> set[str]:
    """주소에서 비교에 쓸 숫자(번지/건물번호) 토큰."""
    return set(_ADDR_NUM_RE.findall(address or ""))


def _parse_date(raw: str | None) -> date | None:
    text = (raw or "").strip()
    if not text:
        return None
    text = text.split(" ")[0].replace("-", "").replace(".", "").replace("/", "")
    if len(text) != 8 or not text.isdigit():
        return None
    try:
        return datetime.strptime(text, "%Y%m%d").date()
    except ValueError:
        return None


def _pick(row: dict[str, str], cols: tuple[str, ...]) -> str:
    for col in cols:
        value = row.get(col)
        if value and value.strip():
            return value.strip()
    return ""


@dataclass(frozen=True)
class BusinessRecord:
    """인허가 대장 1건."""

    name: str
    address: str
    status: str
    opened_on: date | None
    closed_on: date | None

    @property
    def closed(self) -> bool:
        if self.closed_on is not None:
            return True
        return any(word in self.status for word in _CLOSED_STATUSES)


class LocalDataRegistry:
    """상호+주소로 인허가 대장을 조회하는 인메모리 인덱스."""

    def __init__(self) -> None:
        self._by_name: dict[str, list[BusinessRecord]] = {}
        self._loaded_on: date | None = None

    @property
    def loaded(self) -> bool:
        return bool(self._by_name)

    @property
    def loaded_on(self) -> date | None:
        return self._loaded_on

    def is_stale(self, today: date | None = None) -> bool:
        """주 1회 갱신 기준으로 다시 읽어야 하는지."""
        if self._loaded_on is None:
            return True
        return ((today or date.today()) - self._loaded_on).days >= RELOAD_INTERVAL_DAYS

    def clear(self) -> None:
        self._by_name = {}
        self._loaded_on = None

    def adopt(self, other: LocalDataRegistry) -> None:
        """완성된 인덱스로 **원자적으로** 갈아끼운다.

        새 것을 다 채운 뒤 참조만 바꾼다 — 기존 인덱스를 먼저 비우면 그 사이
        요청들이 폐업 필터 없이 지나간다. 조회 중인 쪽은 옛 dict 를 계속 본다.
        """
        self._by_name = other._by_name
        self._loaded_on = other._loaded_on

    # --- 적재 -------------------------------------------------------------
    def load_csv(
        self,
        source: Path | str | Iterable[str],
        *,
        loaded_on: date | None = None,
    ) -> int:
        """CSV 를 **한 줄씩 흘려 읽어** 인덱스에 추가한다. 반환값은 인덱싱한 행 수.

        source 는 파일 경로이거나 줄 이터레이터(테스트용 StringIO 등)다.
        파일 내용을 문자열로 통째로 받지 않는다 — 200MB 파일이 그대로 메모리에
        올라가고, 거기서 만든 레코드까지 더해 OOM 이 난다.
        """
        if isinstance(source, str | Path):
            path = Path(source)
            with path.open(
                encoding=detect_encoding(path), errors="replace", newline=""
            ) as fh:
                return self._ingest(fh, loaded_on=loaded_on, label=path.name)
        return self._ingest(iter(source), loaded_on=loaded_on, label="<stream>")

    def _ingest(
        self, lines: Iterator[str], *, loaded_on: date | None, label: str
    ) -> int:
        started = time.monotonic()
        read = kept = 0
        for row in csv.DictReader(lines):
            read += 1
            name = _pick(row, _NAME_COLS)
            if not name:
                continue
            address = _pick(row, _ADDR_COLS)
            if not _in_target_area(address):
                continue  # 전국 파일의 대부분은 여기서 버려진다
            self._by_name.setdefault(_norm_name(name), []).append(
                BusinessRecord(
                    name=name,
                    address=address,
                    status=_pick(row, _STATUS_COLS),
                    opened_on=_parse_date(_pick(row, _OPENED_COLS)),
                    closed_on=_parse_date(_pick(row, _CLOSED_COLS)),
                )
            )
            kept += 1
        elapsed = time.monotonic() - started
        logger.info(
            "localdata 적재 %s: 읽음 %d행 / 인덱싱 %d행 (%.1f%%) / %.1f초",
            label, read, kept, 100 * kept / max(read, 1), elapsed,
        )
        if read and kept / read > KEEP_RATIO_WARN:
            logger.warning(
                "localdata 인덱싱 비율이 %.1f%% 다 — 시군구 필터가 걸리지 않았을 수 있다"
                " (주소 칼럼명이 바뀌었는지 확인: %s)",
                100 * kept / read, label,
            )
        if kept:
            self._loaded_on = loaded_on or date.today()
        return kept

    def load_dir(self, directory: str | Path, *, loaded_on: date | None = None) -> int:
        """CSV 가 모인 디렉터리를 통째로 적재. 없으면 0."""
        path = Path(directory)
        if not path.is_dir():
            return 0
        return sum(
            self.load_csv(csv_path, loaded_on=loaded_on)
            for csv_path in sorted(path.glob("*.csv"))
        )

    def reload_if_stale(self) -> int:
        """설정된 디렉터리에서 다시 읽는다(설정 없으면 무동작).

        **배치 프로세스 전용이다.** API 요청 경로에서는 절대 부르지 않는다 —
        수백 MB 파싱이 이벤트 루프를 막고, 적재 중인 인덱스를 비워 버린다.
        """
        if not settings.localdata_csv_dir or not self.is_stale():
            return 0
        fresh = LocalDataRegistry()
        count = fresh.load_dir(settings.localdata_csv_dir)
        self.adopt(fresh)
        return count

    # --- 조회 -------------------------------------------------------------
    def find(self, name: str, address: str | None = None) -> BusinessRecord | None:
        """상호로 후보를 찾고, 주소 번지가 겹치는 건을 고른다.

        동명 업소가 여럿이면 주소가 맞아떨어지는 것만 인정한다 — 엉뚱한 지점의
        폐업 기록으로 멀쩡한 장소를 지우는 편이 놓치는 것보다 나쁘다.
        """
        candidates: list[BusinessRecord] = []
        for key in _name_keys(name):
            candidates = self._by_name.get(key) or []
            if candidates:
                break
        if not candidates:
            return None
        if len(candidates) == 1 and not address:
            return candidates[0]
        tokens = _addr_tokens(address)
        if tokens:
            matched = [r for r in candidates if _addr_tokens(r.address) & tokens]
            if matched:
                # 폐업 기록이 있으면 그것을 우선(같은 자리 재개업은 인허가가 새로 난다)
                return next((r for r in matched if r.closed), matched[0])
        return candidates[0] if len(candidates) == 1 else None

    def is_closed(self, name: str, address: str | None = None) -> bool:
        record = self.find(name, address)
        return bool(record and record.closed)

    def opened_on(self, name: str, address: str | None = None) -> date | None:
        record = self.find(name, address)
        return record.opened_on if record else None

    def closure_rate(self, address: str | None) -> float | None:
        """같은 행정동(주소 앞 3토큰) 폐업률. 표본 10건 미만이면 None."""
        area = _area_key(address)
        if not area:
            return None
        records = [
            r
            for group in self._by_name.values()
            for r in group
            if _area_key(r.address) == area
        ]
        if len(records) < 10:
            return None
        return sum(1 for r in records if r.closed) / len(records)


def _area_key(address: str | None) -> str:
    """주소 앞 3토큰(시/구/동)을 지역 키로 쓴다."""
    parts = (address or "").split()
    return " ".join(parts[:3]) if len(parts) >= 3 else ""


def detect_encoding(path: Path) -> str:
    """앞 4KB 만 보고 인코딩을 고른다(200MB 파일을 통째로 읽지 않는다).

    LOCALDATA 신원천은 CP949 다(응답 헤더의 charset=UTF-8 은 사실과 다르다).
    예전에 UTF-8 로 받아 둔 파일도 그대로 읽히도록 판별한다.
    """
    with path.open("rb") as fh:
        head = fh.read(SNIFF_BYTES)
    if head.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    # 끝이 멀티바이트 문자 중간에서 잘렸을 수 있으므로 마지막 3바이트는 버린다
    try:
        head[:-3].decode("utf-8")
    except UnicodeDecodeError:
        return "cp949"
    return "utf-8"


def _in_target_area(address: str) -> bool:
    """우리 상권의 (시도, 시군구) 행만 인덱싱한다(전국 파일에서 99% 는 버려진다).

    시도까지 함께 봐야 부산 중구·대구 중구 같은 동명 시군구가 딸려오지 않는다.
    개방자치단체코드로 거르는 편이 더 정확하지만 공식 코드표를 대조하지 못해
    "미확인"으로 남겼다(docs/DATA_STRATEGY.md). 확인되면 코드 필터를 우선한다.
    """
    if not address:
        return False
    return any(
        sigungu in address and any(alias in address for alias in aliases)
        for aliases, sigungu in _AREA_MATCHERS
    )


@lru_cache(maxsize=1)
def get_localdata_registry() -> LocalDataRegistry:
    """싱글턴. **빈 채로** 돌려준다 — 적재는 기동 시 백그라운드에서 한다.

    여기서 load_dir 을 부르면 첫 요청을 보낸 사용자가 수백 MB 파싱이 끝날 때까지
    수십 초를 기다린다. 적재 전에는 인덱스가 비어 폐업 필터가 무동작(폴백)이다.
    """
    return LocalDataRegistry()


async def warm_localdata() -> int:
    """한 번 적재해 현재 인덱스와 원자적으로 교체한다. 실패해도 서비스는 뜬다."""
    import asyncio

    directory = settings.localdata_csv_dir
    if not directory or not Path(directory).is_dir():
        return 0
    try:
        # 파싱은 CPU·IO 를 오래 잡는다 → 이벤트 루프를 막지 않도록 스레드에서.
        # 새 레지스트리에 다 채운 뒤 갈아끼워, 적재 중에도 조회가 계속 된다.
        fresh = LocalDataRegistry()
        count = await asyncio.to_thread(fresh.load_dir, directory)
        if count:
            get_localdata_registry().adopt(fresh)
        return count
    except Exception:
        logger.exception("localdata 적재 실패 — 폐업 필터 없이 계속한다")
        return 0


REFRESH_CHECK_INTERVAL_SEC = 24 * 60 * 60  # 하루 한 번 갱신 여부만 본다


async def localdata_refresher(
    interval_sec: int = REFRESH_CHECK_INTERVAL_SEC,
) -> None:
    """기동 직후 1회 + 이후 주기적으로 적재한다(lifespan 이 취소할 때까지).

    요청 경로에서 적재하지 않기 위한 짝이다 — 크론이 새 CSV 를 내려받아도
    API 프로세스의 인덱스는 여기서만 갱신된다.
    """
    import asyncio

    await warm_localdata()
    while True:
        await asyncio.sleep(interval_sec)
        if get_localdata_registry().is_stale():
            await warm_localdata()
