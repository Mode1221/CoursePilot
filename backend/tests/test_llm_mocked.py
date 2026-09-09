"""LLM 경로(도구 호출)를 가짜 클라이언트로 검증. 실제 키 없이 동작 보장."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app import llm_client
from app.config import settings
from app.metrics import metrics_store
from app.pipeline.llm import _TOOL_NAME, decompose
from app.schemas import TravelMode


class _FakeAnthropic:
    """messages.create 가 tool_use 블록을 돌려주는 최소 스텁."""

    def __init__(self, blocks, *, raises: Exception | None = None):
        self._blocks = blocks
        self._raises = raises
        self.calls: list[dict] = []
        self.messages = SimpleNamespace(create=self._create)

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._raises is not None:
            raise self._raises
        return SimpleNamespace(content=self._blocks)


def _tool_block(payload: dict, *, name: str = _TOOL_NAME):
    return SimpleNamespace(type="tool_use", name=name, input=payload)


class _FakeOpenAI:
    def __init__(self, arguments: str):
        self._arguments = arguments
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        call = SimpleNamespace(
            function=SimpleNamespace(name=_TOOL_NAME, arguments=self._arguments)
        )
        message = SimpleNamespace(tool_calls=[call])
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _ext() -> dict:
    for e in metrics_store.snapshot()["externals"]:
        if e["name"] == "llm.decompose":
            return e
    raise AssertionError("llm.decompose 집계 없음")


@pytest.fixture(autouse=True)
def _reset_metrics():
    metrics_store.clear()
    yield


def _use_anthropic(monkeypatch, client):
    monkeypatch.setattr(settings, "llm_provider", "anthropic")
    monkeypatch.setattr(llm_client, "get_anthropic_client", lambda: client)


def _use_openai(monkeypatch, client):
    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(llm_client, "get_openai_client", lambda: client)


async def test_anthropic_도구호출_결과를_제약으로_변환한다(monkeypatch):
    client = _FakeAnthropic(
        [
            SimpleNamespace(type="text", text="무시되는 서두"),
            _tool_block(
                {
                    "region": "연남동",
                    "start_time": "19:00",
                    "duration_min": 180,
                    "travel_mode": "transit",
                    "party_size": 4,
                    "stop_count": 3,
                    "budget_max": 40000,
                    "keywords": ["와인"],
                    "exclude_keywords": ["술집"],
                }
            ),
        ]
    )
    _use_anthropic(monkeypatch, client)

    c = await decompose("아무 문장")

    assert c.region == "연남동"
    assert c.start_time.hour == 19
    assert c.duration_min == 180
    assert c.travel_mode == TravelMode.TRANSIT
    assert c.party_size == 4
    assert c.stop_count == 3
    assert c.budget_max == 40000
    assert "와인" in c.keywords
    assert c.exclude_keywords == ["술집"]


async def test_anthropic_요청에_도구_강제_지정이_실린다(monkeypatch):
    client = _FakeAnthropic([_tool_block({"region": "성수동"})])
    _use_anthropic(monkeypatch, client)

    await decompose("성수동 가자")

    sent = client.calls[0]
    assert sent["tool_choice"] == {"type": "tool", "name": _TOOL_NAME}
    assert sent["tools"][0]["name"] == _TOOL_NAME
    assert sent["messages"] == [{"role": "user", "content": "성수동 가자"}]
    props = sent["tools"][0]["input_schema"]["properties"]
    assert {"region", "stop_count", "exclude_keywords"} <= set(props)


async def test_도구호출이_없으면_규칙파서로_폴백(monkeypatch):
    client = _FakeAnthropic([SimpleNamespace(type="text", text="설명만 함")])
    _use_anthropic(monkeypatch, client)

    c = await decompose("성수동 오후 1시 3시간")

    assert c.region == "성수동"  # 규칙 파서 결과
    assert _ext()["fallback"] == 1


async def test_LLM_예외는_폴백으로_흡수된다(monkeypatch):
    client = _FakeAnthropic([], raises=RuntimeError("boom"))
    _use_anthropic(monkeypatch, client)

    c = await decompose("성수동 오후 1시 3시간")

    assert c.region == "성수동"
    assert _ext()["fallback"] == 1


async def test_성공하면_성공으로_집계한다(monkeypatch):
    _use_anthropic(monkeypatch, _FakeAnthropic([_tool_block({"region": "성수동"})]))

    await decompose("아무 문장")

    ext = _ext()
    assert ext["ok"] == 1 and ext["fallback"] == 0


async def test_openai_함수호출_인자를_파싱한다(monkeypatch):
    client = _FakeOpenAI(json.dumps({"region": "익선동", "party_size": 2}))
    _use_openai(monkeypatch, client)

    c = await decompose("아무 문장")

    assert c.region == "익선동"
    assert c.party_size == 2
    sent = client.calls[0]
    assert sent["tool_choice"]["function"]["name"] == _TOOL_NAME


async def test_openai_응답이_깨져도_폴백(monkeypatch):
    _use_openai(monkeypatch, _FakeOpenAI("{not json"))

    c = await decompose("성수동 오후 1시 3시간")

    assert c.region == "성수동"


async def test_클라이언트가_없으면_규칙파서(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "anthropic")
    monkeypatch.setattr(llm_client, "get_anthropic_client", lambda: None)

    c = await decompose("성수동 오후 1시 3시간")

    assert c.region == "성수동"
    assert _ext()["fallback"] == 1
