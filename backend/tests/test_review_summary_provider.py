"""리뷰 요약도 조건 분해와 같은 LLM 프로바이더 설정을 따른다."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app import llm_client
from app.config import settings
from app.metrics import metrics_store
from app.reviews.rag import summarize_reviews

_REVIEWS = ["웨이팅이 길지만 맛있어요", "주차가 편했어요"]


@pytest.fixture(autouse=True)
def _clean():
    metrics_store.clear()
    yield
    metrics_store.clear()


class _FakeAnthropic:
    def __init__(self, text: str | None = "요약된 내용", raises: Exception | None = None):
        self._text = text
        self._raises = raises
        self.calls: list[dict] = []
        self.messages = SimpleNamespace(create=self._create)

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._raises:
            raise self._raises
        blocks = [SimpleNamespace(type="text", text=self._text)] if self._text else []
        return SimpleNamespace(content=blocks)


async def test_기본_프로바이더는_anthropic(monkeypatch):
    client = _FakeAnthropic()
    monkeypatch.setattr(settings, "llm_provider", "anthropic")
    monkeypatch.setattr(llm_client, "get_anthropic_client", lambda: client)

    assert await summarize_reviews(_REVIEWS) == "요약된 내용"
    assert client.calls[0]["model"] == settings.anthropic_model


async def test_openai_설정이면_openai를_쓴다(monkeypatch):
    calls: list[dict] = []

    class _FakeOpenAI:
        def __init__(self):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

        async def _create(self, **kwargs):
            calls.append(kwargs)
            message = SimpleNamespace(content="OpenAI 요약")
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(llm_client, "get_openai_client", lambda: _FakeOpenAI())

    assert await summarize_reviews(_REVIEWS) == "OpenAI 요약"
    assert calls


async def test_실패하면_태그_요약으로_폴백(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "anthropic")
    monkeypatch.setattr(
        llm_client, "get_anthropic_client", lambda: _FakeAnthropic(raises=RuntimeError("x"))
    )

    out = await summarize_reviews(_REVIEWS)
    assert "리뷰" in out  # 태그 기반 폴백 문구
    ext = {e["name"]: e for e in metrics_store.snapshot()["externals"]}
    assert ext["llm.review_summary"]["fallback"] == 1


async def test_키가_없으면_폴백(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "anthropic")
    monkeypatch.setattr(llm_client, "get_anthropic_client", lambda: None)

    assert "리뷰" in await summarize_reviews(_REVIEWS)


async def test_리뷰가_없으면_안내문():
    assert await summarize_reviews([]) == "참고할 리뷰가 없습니다."
