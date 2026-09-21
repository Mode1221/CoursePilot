"""전국 파일을 올려도 메모리가 터지지 않는지.

일반음식점 전국 파일은 200만 행이 넘고 운영 VM 은 6GB 다. 파일을 통째로 읽거나
전 행을 인덱싱하면 백엔드가 OOM 으로 죽는다 — 스트리밍 + 시군구 필터를 고정한다.
"""
import io
import tracemalloc

from app.adapters.localdata import (
    TARGET_SIGUNGU,
    LocalDataRegistry,
    detect_encoding,
)

HEADER = (
    "개방자치단체코드,사업장명,도로명주소,지번주소,영업상태명,상세영업상태명,"
    "인허가일자,폐업일자\n"
)
ROWS = 500_000
TARGET_EVERY = 50  # 2% 만 우리 상권 시군구
PEAK_LIMIT_MB = 100


def _write_national_csv(path, rows=ROWS):
    """CP949 합성 전국 파일. 대부분은 우리가 안 쓰는 지역이다."""
    with path.open("w", encoding="cp949", newline="") as fh:
        fh.write(HEADER)
        for i in range(rows):
            if i % TARGET_EVERY == 0:
                addr = f"서울특별시 성동구 아차산로 {i}"
            else:
                addr = f"부산광역시 해운대구 센텀로 {i}"
            fh.write(f"300{i % 9}000,가게{i},{addr},{addr},영업/정상,영업,20200101,\n")
    return path


def test_전국_파일을_올려도_피크_메모리가_100MB_미만(tmp_path):
    directory = tmp_path / "localdata"
    directory.mkdir()
    _write_national_csv(directory / "general_restaurants.csv")

    registry = LocalDataRegistry()
    tracemalloc.start()
    kept = registry.load_dir(directory)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert kept == ROWS // TARGET_EVERY  # 2% 만 인덱싱
    peak_mb = peak / 1e6
    assert peak_mb < PEAK_LIMIT_MB, f"피크 {peak_mb:.0f}MB (상한 {PEAK_LIMIT_MB}MB)"


def test_대상_시군구가_아닌_행은_버린다():
    registry = LocalDataRegistry()
    kept = registry.load_csv(
        io.StringIO(
            HEADER
            + "3040000,밖에있는집,부산광역시 해운대구 센텀로 1,,영업/정상,영업,20200101,\n"
            + "3040000,안에있는집,서울특별시 성동구 아차산로 1,,영업/정상,영업,20200101,\n"
        )
    )
    assert kept == 1
    assert registry.find("안에있는집") is not None
    assert registry.find("밖에있는집") is None


def test_대상_시군구_목록이_24개_상권을_덮는다():
    from app.batch.districts import DISTRICTS

    assert TARGET_SIGUNGU == {d.sigungu for d in DISTRICTS}
    assert len(TARGET_SIGUNGU) == 11


def test_인코딩을_앞부분만_보고_판별한다(tmp_path):
    cp949 = tmp_path / "a.csv"
    cp949.write_text(HEADER + "3040000,한글집,서울특별시 성동구 1,,영업,영업,20200101,\n",
                     encoding="cp949")
    utf8 = tmp_path / "b.csv"
    utf8.write_text(HEADER, encoding="utf-8-sig")
    assert detect_encoding(cp949) == "cp949"
    assert detect_encoding(utf8) == "utf-8-sig"


def test_적재_중에도_이전_스냅샷으로_조회된다(tmp_path):
    """적재는 새 레지스트리에 채운 뒤 갈아끼운다 — 그 사이 조회가 비지 않는다.

    기존처럼 인덱스를 먼저 clear() 하면, 적재가 도는 수십 초 동안 폐업한 가게가
    그대로 코스에 들어간다.
    """
    import threading

    registry = LocalDataRegistry()
    registry.load_csv(
        io.StringIO(
            HEADER
            + "3040000,예전집,서울특별시 성동구 아차산로 1,,폐업,폐업,20100101,20200101\n"
        )
    )
    assert registry.is_closed("예전집") is True

    big = tmp_path / "big.csv"
    _write_national_csv(big, rows=200_000)
    with big.open("a", encoding="cp949", newline="") as fh:  # 새 대장에도 같은 폐업 건
        fh.write("3040000,예전집,서울특별시 성동구 아차산로 1,,폐업,폐업,20100101,20200101\n")

    seen: list[bool] = []
    errors: list[BaseException] = []

    def reload_into_snapshot():
        try:
            fresh = LocalDataRegistry()
            fresh.load_csv(big)
            registry.adopt(fresh)  # 다 채운 뒤에만 갈아끼운다
        except BaseException as exc:  # noqa: BLE001 - 테스트에서 원인을 보려고
            errors.append(exc)

    worker = threading.Thread(target=reload_into_snapshot)
    worker.start()
    while worker.is_alive():
        # 적재가 도는 동안 계속 조회한다 — 예외도, 빈 결과도 나오면 안 된다
        seen.append(registry.is_closed("예전집"))
    worker.join()

    assert not errors
    # 적재 중에도, 교체 뒤에도 한 번도 비지 않아야 한다
    assert len(seen) > 10 and all(seen), "적재 중에 폐업 판정이 비었다"
    assert registry.loaded  # 교체 후에도 인덱스는 채워져 있다


def test_동명_시군구가_딸려오지_않는다():
    """'중구'는 부산·대구·인천에도 있다 — 시도까지 맞아야 담는다."""
    registry = LocalDataRegistry()
    kept = registry.load_csv(
        io.StringIO(
            HEADER
            + "2600000,부산중구집,부산광역시 중구 광복로 1,,영업/정상,영업,20200101,\n"
            + "3000000,서울중구집,서울특별시 중구 을지로 1,,영업/정상,영업,20200101,\n"
            + "4100000,판교집,경기도 성남시 분당구 판교역로 1,,영업/정상,영업,20200101,\n"
        )
    )
    assert kept == 2
    assert registry.find("부산중구집") is None
    assert registry.find("서울중구집") is not None
    assert registry.find("판교집") is not None


# ── 인덱스 캐시 ───────────────────────────────────────────────────────────
def _write_csv(directory, name, rows):
    header = "개방자치단체코드,사업장명,도로명주소,지번주소,영업상태명,상세영업상태명,인허가일자,폐업일자\n"
    (directory / name).write_text(header + rows, encoding="cp949")


def test_두_번째_적재는_캐시에서_되살린다(tmp_path):
    from app.adapters.localdata import CACHE_FILE, LocalDataRegistry

    _write_csv(tmp_path, "rest_cafes.csv",
               "3040000,살아있는집,서울특별시 성동구 아차산로 17,,영업/정상,영업,20150301,\n")
    first = LocalDataRegistry()
    assert first.load_dir(tmp_path) == 1
    assert (tmp_path / CACHE_FILE).exists()

    # 같은 CSV(같은 이름·크기·mtime)면 파싱 없이 캐시에서 되살아난다
    second = LocalDataRegistry()
    assert second.load_dir(tmp_path) == 1
    assert second.find("살아있는집", "서울특별시 성동구 아차산로 17") is not None
    assert second.loaded_on == first.loaded_on


def test_원본_CSV_가_바뀌면_캐시를_버린다(tmp_path):
    import os
    import time

    from app.adapters.localdata import LocalDataRegistry

    _write_csv(tmp_path, "rest_cafes.csv",
               "3040000,살아있는집,서울특별시 성동구 아차산로 17,,영업/정상,영업,20150301,\n")
    LocalDataRegistry().load_dir(tmp_path)
    # 내용이 바뀌고(크기 변화) mtime 도 앞으로
    _write_csv(tmp_path, "rest_cafes.csv",
               "3040000,살아있는집,서울특별시 성동구 아차산로 17,,영업/정상,영업,20150301,\n"
               "3040000,새로생긴집,서울특별시 성동구 아차산로 19,,영업/정상,영업,20250301,\n")
    later = time.time() + 5
    os.utime(tmp_path / "rest_cafes.csv", (later, later))
    fresh = LocalDataRegistry()
    assert fresh.load_dir(tmp_path) == 2
    assert fresh.find("새로생긴집", "서울특별시 성동구 아차산로 19") is not None


def test_캐시가_깨져_있으면_CSV_로_돌아간다(tmp_path):
    from app.adapters.localdata import CACHE_FILE, LocalDataRegistry

    _write_csv(tmp_path, "rest_cafes.csv",
               "3040000,살아있는집,서울특별시 성동구 아차산로 17,,영업/정상,영업,20150301,\n")
    (tmp_path / CACHE_FILE).write_bytes(b"not a pickle")
    assert LocalDataRegistry().load_dir(tmp_path) == 1


def test_use_cache_False_는_캐시를_만들지_않는다(tmp_path):
    from app.adapters.localdata import CACHE_FILE, LocalDataRegistry

    _write_csv(tmp_path, "rest_cafes.csv",
               "3040000,살아있는집,서울특별시 성동구 아차산로 17,,영업/정상,영업,20150301,\n")
    assert LocalDataRegistry().load_dir(tmp_path, use_cache=False) == 1
    assert not (tmp_path / CACHE_FILE).exists()
