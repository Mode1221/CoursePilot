"""LOCALDATA 파일이 24개 상권의 시군구를 덮는지."""
import pytest

from app.batch.coverage import covered_sigungu, missing_districts, required_sigungu
from app.batch.districts import DISTRICTS

HEADER = "개방자치단체코드,사업장명,도로명주소,지번주소,영업상태명,상세영업상태명,인허가일자,폐업일자\n"


def _csv(tmp_path, name: str, addresses: list[str]):
    rows = "".join(
        f"3040000,가게{i},{addr},{addr},영업/정상,영업,20200101,\n"
        for i, addr in enumerate(addresses)
    )
    path = tmp_path / name
    # 실제 파일은 CP949 다(응답 헤더의 charset=UTF-8 은 사실과 다르다).
    path.write_text(HEADER + rows, encoding="cp949")
    return path


def test_모든_상권에_시군구가_지정돼_있다():
    """시군구가 비면 그 상권은 폐업 판정에서 조용히 빠진다."""
    assert [d.name for d in DISTRICTS if not d.sigungu] == []


def test_시군구별로_어느_상권이_걸리는지_안다():
    mapping = required_sigungu()
    assert mapping["성동구"] == ["성수"]
    assert set(mapping["마포구"]) == {"연남", "홍대", "합정", "망원"}
    assert sum(len(v) for v in mapping.values()) == len(DISTRICTS)


def test_있는_파일의_시군구를_찾아낸다(tmp_path):
    _csv(tmp_path, "seongdong.csv", ["서울특별시 성동구 성수이로 100"])
    _csv(tmp_path, "mapo.csv", ["서울특별시 마포구 연남로 20"])
    covered = covered_sigungu(tmp_path)
    assert set(covered) == {"성동구", "마포구"}
    assert covered["성동구"] == ["seongdong.csv"]


def test_없는_시군구와_영향받는_상권을_알려준다(tmp_path):
    _csv(tmp_path, "seongdong.csv", ["서울특별시 성동구 성수이로 100"])
    missing = missing_districts(tmp_path)
    assert "성동구" not in missing
    assert set(missing["종로구"]) == {"종로", "익선동", "서촌", "북촌", "대학로"}


def test_디렉터리가_없으면_전부_미커버로_본다(tmp_path):
    assert len(missing_districts(tmp_path / "없음")) == len(required_sigungu())


def test_주소_컬럼이_없는_파일은_무시한다(tmp_path):
    (tmp_path / "이상.csv").write_text("아무거나,값\n1,2\n", encoding="utf-8")
    assert covered_sigungu(tmp_path) == {}


def test_전국_파일_한_개로_24개_상권을_모두_덮는다(tmp_path):
    """신원천은 업종별 전국 파일이다 — 파일 하나가 11개 시군구를 다 담는다."""
    addresses = [f"서울특별시 {d.sigungu} {d.name}로 10" for d in DISTRICTS]
    _csv(tmp_path, "general_restaurants.csv", addresses)
    assert missing_districts(tmp_path) == {}
    assert len(covered_sigungu(tmp_path)) == len(required_sigungu())


def test_앞부분에_없는_시군구도_찾아낸다(tmp_path):
    """전국 파일은 자치단체코드 순이라 서울 일부가 한참 뒤에 나온다.

    예전처럼 앞 300행만 보면 그 상권의 폐업 판정이 통째로 빠진 채 지나간다.
    """
    filler = ["부산광역시 해운대구 센텀로 1"] * 1000
    _csv(tmp_path, "nationwide.csv", filler + ["서울특별시 종로구 삼일대로 30"])
    assert "종로구" in covered_sigungu(tmp_path)


def test_CP949_파일을_읽는다(tmp_path):
    """응답 헤더는 charset=UTF-8 이라 하지만 실제 본문은 CP949 다."""
    path = _csv(tmp_path, "cp949.csv", ["서울특별시 용산구 이태원로 100"])
    with pytest.raises(UnicodeDecodeError):  # UTF-8 로는 못 읽는 파일이다
        path.read_text(encoding="utf-8")
    assert "용산구" in covered_sigungu(tmp_path)
