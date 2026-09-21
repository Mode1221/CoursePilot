"""배치 진입점의 LOCALDATA 동기 적재 — 별개 프로세스라 lifespan 이 없다."""

import io

from app.adapters import localdata as ld
from app.batch.localdata_boot import load_localdata_or_exit
from app.config import settings

CSV = """개방자치단체코드,사업장명,도로명주소,지번주소,영업상태명,상세영업상태명,인허가일자,폐업일자
3040000,살아있는집,서울 성동구 아차산로 17,서울 성동구 성수동2가 17,영업/정상,영업,20150301,
"""


def _fresh_registry(monkeypatch):
    registry = ld.LocalDataRegistry()
    monkeypatch.setattr(ld, "get_localdata_registry", lambda: registry)
    return registry


def test_디렉터리가_설정돼_있으면_동기_적재한다(tmp_path, monkeypatch):
    (tmp_path / "rest_cafes.csv").write_text(CSV, encoding="utf-8")
    monkeypatch.setattr(settings, "localdata_csv_dir", str(tmp_path))
    registry = _fresh_registry(monkeypatch)
    assert load_localdata_or_exit() is True
    assert registry.loaded and registry.find("살아있는집", "서울 성동구 아차산로 17")


def test_설정됐는데_비어_있으면_기본은_중단(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "localdata_csv_dir", str(tmp_path))
    _fresh_registry(monkeypatch)
    assert load_localdata_or_exit() is False
    assert load_localdata_or_exit(allow_missing=True) is True


def test_미설정이면_경고만_하고_진행(monkeypatch):
    monkeypatch.setattr(settings, "localdata_csv_dir", "")
    _fresh_registry(monkeypatch)
    assert load_localdata_or_exit() is True


def test_drop_closed_가_빈_레지스트리를_스스로_채운다(tmp_path, monkeypatch):
    from app.batch.places_build import drop_closed
    from app.schemas import Place

    (tmp_path / "rest_cafes.csv").write_text(
        CSV
        + "3040000,문닫은집,서울 성동구 아차산로 21,서울 성동구 성수동2가 21,폐업,폐업,20180401,20220501\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "localdata_csv_dir", str(tmp_path))
    _fresh_registry(monkeypatch)
    places = [
        Place(id="a", name="살아있는집", address="서울 성동구 아차산로 17", lat=37.5, lng=127.0),
        Place(id="b", name="문닫은집", address="서울 성동구 아차산로 21", lat=37.5, lng=127.0),
    ]
    kept, removed = drop_closed(places)
    assert [p.id for p in kept] == ["a"] and removed == 1


def test_이미_적재됐으면_다시_읽지_않는다(tmp_path, monkeypatch):
    registry = _fresh_registry(monkeypatch)
    registry.load_csv(io.StringIO(CSV))
    monkeypatch.setattr(settings, "localdata_csv_dir", str(tmp_path))
    assert ld.ensure_loaded_for_batch() == 0
    assert registry.loaded
