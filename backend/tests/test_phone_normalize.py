"""표기가 달라도 같은 번호는 같은 계정이다."""
from fastapi.testclient import TestClient

from app.auth import normalize_phone
from app.main import api

client = TestClient(api)


def test_표기를_숫자만_남긴_한_가지로_맞춘다():
    same = ["010-1234-5678", "01012345678", "+82 10-1234-5678", "010 1234 5678 "]
    assert len({normalize_phone(p) for p in same}) == 1
    assert normalize_phone("+82 10-1234-5678") == "01012345678"


def test_같은_번호를_다르게_적어도_같은_계정으로_들어간다():
    first = client.post("/signup", json={"phone": "010-9876-5432"}).json()
    again = client.post("/signup", json={"phone": "+82 10 9876 5432"}).json()
    # 표기만 다른 재가입으로 새 계정(=새 무료 크레딧)이 생기면 안 된다
    assert again["user_id"] == first["user_id"]


def test_다른_번호는_다른_계정이다():
    a = client.post("/signup", json={"phone": "010-1111-2222"}).json()
    b = client.post("/signup", json={"phone": "010-1111-2223"}).json()
    assert a["user_id"] != b["user_id"]
