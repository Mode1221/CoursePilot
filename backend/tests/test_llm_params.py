"""모델·effort 설정: 5.x 는 도구 강제 호출을 쓰지 않고, effort 는 지원 모델에만 싣는다."""
from app.config import settings
from app.llm_client import THINKING_ROOM, anthropic_params


def test_하이쿠는_지금처럼_도구_강제_effort_없음(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_model", "claude-haiku-4-5")
    monkeypatch.setattr(settings, "anthropic_effort", "high")
    p = anthropic_params(512, "추출기", "set_constraints")
    assert p["tool_choice"] == {"type": "tool", "name": "set_constraints"}
    assert "extra_body" not in p and p["max_tokens"] == 512
    assert p["system"] == "추출기"


def test_소넷_5_5_high는_auto_도구와_effort(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_model", "claude-sonnet-5-5")
    monkeypatch.setattr(settings, "anthropic_effort", "high")
    p = anthropic_params(512, "추출기", "set_constraints")
    assert p["tool_choice"] == {"type": "auto"}
    assert "set_constraints" in p["system"]
    assert p["extra_body"] == {"output_config": {"effort": "high"}}
    assert p["max_tokens"] == 512 + THINKING_ROOM


def test_effort_를_비우면_모델_기본값(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_model", "claude-sonnet-5-5")
    monkeypatch.setattr(settings, "anthropic_effort", "")
    p = anthropic_params(200)
    assert "extra_body" not in p and "tool_choice" not in p and "system" not in p
    assert p["max_tokens"] == 200 + THINKING_ROOM  # 기본 high 로 생각할 자리
