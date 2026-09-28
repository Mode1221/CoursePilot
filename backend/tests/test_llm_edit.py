"""LLM 코스 수정 해석 — 규칙 파서가 놓치던 자유 표현."""
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.pipeline.edit import EditCommand
from app.pipeline.llm_edit import ConditionChange, to_command


def test_도구_인자를_편집_명령으로_바꾼다():
    assert to_command({"action": "replace", "positions": [2], "search": "공원"}, 3) == EditCommand(
        action="replace", index=1, keyword="공원"
    )
    assert to_command({"action": "remove", "positions": [1, 3]}, 3).indexes == [0, 2]
    assert to_command({"action": "add", "search": "디저트"}, 2).index == -1
    assert to_command({"action": "swap", "positions": [1, 2]}, 2).index2 == 1
    assert to_command({"action": "condition", "condition": "저렴한"}, 2) == ConditionChange("저렴한")


def test_범위_밖_번호나_빈_값은_버린다():
    """모델이 틀려도 엉뚱한 칸을 건드리지 않는다 — 규칙 결과로 돌아간다."""
    assert to_command({"action": "replace", "positions": [9], "search": "공원"}, 3) is None
    assert to_command({"action": "add", "search": ""}, 3) is None
    assert to_command({"action": "new_course"}, 3) is None
    assert to_command({"action": "condition", "condition": ""}, 3) is None


class _FakeAnthropic:
    def __init__(self, args):
        self.args = args
        self.prompts: list[str] = []
        self.messages = self

    async def create(self, **kw):
        self.prompts.append(kw["messages"][0]["content"])
        block = SimpleNamespace(type="tool_use", name=kw["tool_choice"]["name"], input=self.args)
        return SimpleNamespace(content=[block])


def _client_and_course(monkeypatch):
    from app.main import api
    from app.users import user_store

    c = TestClient(api)
    u = user_store.create("010-7777-8888")
    headers = {"X-User-Id": u.id}
    cid = c.post("/courses", json={"owner_id": u.id}, headers=headers).json()["id"]
    first = c.post(f"/courses/{cid}/generate", json={"text": "성수 저녁 데이트"}, headers=headers).json()
    return c, cid, headers, first["course"]["items"]


def test_카페_대신_공원은_카페_자리를_바꾼다(monkeypatch):
    c, cid, headers, items = _client_and_course(monkeypatch)
    cafe_pos = next(i for i, it in enumerate(items, 1) if it["place"]["category"] == "cafe")
    fake = _FakeAnthropic({"action": "replace", "positions": [cafe_pos], "search": "공원"})
    monkeypatch.setattr("app.llm_client.get_anthropic_client", lambda: fake)

    res = c.post(f"/courses/{cid}/generate", json={"text": "카페 대신 산책할 데로"}, headers=headers)
    after = res.json()["course"]["items"]
    assert fake.prompts and "현재 코스" in fake.prompts[0]  # 코스 목록을 보고 판단한다
    assert len(after) == len(items)  # 추가가 아니라 교체
    assert after[cafe_pos - 1]["place"]["id"] != items[cafe_pos - 1]["place"]["id"]


def test_너무_비싸는_조건을_바꿔_다시_짠다(monkeypatch):
    c, cid, headers, items = _client_and_course(monkeypatch)
    fake = _FakeAnthropic({"action": "condition", "condition": "저렴한"})
    monkeypatch.setattr("app.llm_client.get_anthropic_client", lambda: fake)

    res = c.post(f"/courses/{cid}/generate", json={"text": "너무 비싸"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["course"]["items"]  # 되묻지 않고 코스를 다시 만든다


def test_되돌려줘는_직전_변경_전으로_한번_더면_다시_앞으로(monkeypatch):
    c, cid, headers, items = _client_and_course(monkeypatch)
    before = [it["place"]["id"] for it in items]
    c.post(f"/courses/{cid}/generate", json={"text": "마지막 삭제"}, headers=headers)
    undo = c.post(f"/courses/{cid}/generate", json={"text": "되돌려줘"}, headers=headers).json()
    assert [it["place"]["id"] for it in undo["course"]["items"]] == before
    redo = c.post(f"/courses/{cid}/generate", json={"text": "되돌려줘"}, headers=headers).json()
    assert len(redo["course"]["items"]) == len(before) - 1


def test_되돌릴_것이_없으면_그대로_알린다(monkeypatch):
    c, cid, headers, items = _client_and_course(monkeypatch)
    res = c.post(f"/courses/{cid}/generate", json={"text": "원래대로 해줘"}, headers=headers).json()
    assert [it["place"]["id"] for it in res["course"]["items"]] == [it["place"]["id"] for it in items]


def test_키가_없으면_규칙_파서_그대로(monkeypatch):
    c, cid, headers, items = _client_and_course(monkeypatch)
    res = c.post(f"/courses/{cid}/generate", json={"text": "마지막 삭제"}, headers=headers)
    assert len(res.json()["course"]["items"]) == len(items) - 1
