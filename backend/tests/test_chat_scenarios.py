"""채팅 시나리오 회귀 — 실제로 사람들이 코스 뒤에 하는 말 25가지.

2026-09-28 평가에서 절반 가까이가 엉뚱하게 동작했다(새 코스로 갈아엎기, 되묻기, 시각 오해).
고친 동작이 조용히 깨지지 않도록 문장별 기대를 고정한다(키 없는 규칙 경로 기준).
"""
import pytest
from fastapi.testclient import TestClient

BASE = "성수동 오전 10시 5시간 도보"


@pytest.fixture
def chat(monkeypatch):
    from app.config import settings
    from app.main import api
    from app.users import user_store

    monkeypatch.setattr(settings, "rate_limit_per_min", 100_000)
    client = TestClient(api)
    user = user_store.create("010-9090-0000")
    headers = {"X-User-Id": user.id}

    def start():
        cid = client.post("/courses", json={"owner_id": user.id}, headers=headers).json()["id"]
        first = client.post(f"/courses/{cid}/generate", json={"text": BASE}, headers=headers).json()
        return cid, first["course"]["items"]

    def say(cid, text):
        body = client.post(f"/courses/{cid}/generate", json={"text": text}, headers=headers).json()
        last = client.get(f"/courses/{cid}/messages", headers=headers).json()[-1]["text"]
        return body["course"]["items"], last

    return start, say


def _ids(items):
    return [it["place"]["id"] for it in items]


def test_끝_시각(chat):
    start, say = chat
    cid, before = start()
    after, reply = say(cid, "3시에 끝나게 해줘")
    assert after[0]["arrive"] == before[0]["arrive"]  # 시작은 그대로
    assert after[-1]["depart"] <= "15:00:00"
    assert "지역을 못 알아들어" not in reply


@pytest.mark.parametrize("text,start_at", [("1시간 늦게 시작하자", "11:"), ("30분 늦게", "10:30"), ("점심으로", "12:")])
def test_시작_시각_바꾸기(chat, text, start_at):
    start, say = chat
    cid, _ = start()
    after, _ = say(cid, text)
    assert after and after[0]["arrive"].startswith(start_at)


@pytest.mark.parametrize("text", ["한 곳 더", "한 곳 더 추가", "하나 더"])
def test_한_곳_더(chat, text):
    start, say = chat
    cid, before = start()
    after, reply = say(cid, text)
    assert len(after) == len(before) + 1 and "추가했어요" in reply


@pytest.mark.parametrize("text", ["아 너무 멀다", "걷기 싫어 차로 갈게", "더 저렴하게", "디저트 먹고 싶어", "좀 덜 붐비는 데로"])
def test_조건_불만은_되묻지_않고_반영한다(chat, text):
    start, say = chat
    cid, _ = start()
    after, reply = say(cid, text)
    assert after, text
    assert "어떤 모임인지" not in reply and "지역을 못 알아들어" not in reply


def test_질문은_코스를_바꾸지_않는다(chat):
    start, say = chat
    cid, before = start()
    for q, expect in [("2번째 어디야?", "2번째는"), ("몇 시에 끝나?", "끝나요"), ("바꿔줄 수 있어?", "말로 고칠 수")]:
        after, reply = say(cid, q)
        assert _ids(after) == _ids(before) and expect in reply, q


def test_되돌리기_왕복(chat):
    start, say = chat
    cid, before = start()
    say(cid, "마지막 삭제")
    undone, _ = say(cid, "되돌려줘")
    assert _ids(undone) == _ids(before)
    redone, _ = say(cid, "되돌려줘")
    assert len(redone) == len(before) - 1


def test_다시_해줘는_바꾸되_곳_수를_지킨다(chat):
    start, say = chat
    cid, before = start()
    after, reply = say(cid, "다시 해줘")
    assert len(after) >= len(before) and _ids(after) != _ids(before)
    assert "새로 골랐어요" in reply


def test_싫은_곳만_교체하고_시작_시각은_그대로(chat):
    start, say = chat
    cid, before = start()
    after, reply = say(cid, "첫번째 빼고 다 좋아")
    assert len(after) == len(before) and after[0]["place"]["id"] != before[0]["place"]["id"]
    assert after[0]["arrive"] == before[0]["arrive"] and "바꿨어요" in reply


def test_지목한_곳만_남기기(chat):
    start, say = chat
    cid, before = start()
    after, _ = say(cid, "첫번째만 남기고 다 지워")
    assert _ids(after) == _ids(before)[:1]


def test_지역_바꾸기는_시간을_유지한다(chat):
    start, say = chat
    cid, before = start()
    after, _ = say(cid, "홍대로 바꿔줘")
    assert after and after[0]["arrive"] == before[0]["arrive"]
    assert all("홍대" in it["place"]["name"] for it in after)
