"""Thinking parameters for Claude 5.x models (think by default, reject budget_tokens)."""

import pytest

from backend.core.claude_thinking import apply_claude_thinking, claude_thinking_profile
from backend.core.llm_router import GameMasterLLM
from backend.models.user import User


@pytest.mark.parametrize(
    ("model", "budget", "on_by_default", "off_mode"),
    [
        ("openrouter/anthropic/claude-haiku-5.5", False, True, {"type": "disabled"}),
        ("claude-haiku-5-5", False, True, {"type": "disabled"}),
        ("anthropic/claude-sonnet-5.5", False, True, {"type": "between_tools"}),
        ("claude-sonnet-5", False, True, {"type": "disabled"}),
        ("claude-opus-5-5", False, True, None),
        ("claude-opus-5", False, True, {"type": "disabled"}),
        ("claude-opus-4-7", False, False, {"type": "disabled"}),
        ("claude-fable-5-1", False, True, None),
        ("claude-haiku-4-5-20251001", True, False, None),
        ("claude-sonnet-4-20250514", True, False, None),
        ("anthropic/claude-sonnet-4.6", True, False, None),
    ],
)
def test_claude_thinking_profile(model, budget, on_by_default, off_mode):
    profile = claude_thinking_profile(model)
    assert profile is not None
    assert profile.budget_tokens is budget
    assert profile.on_by_default is on_by_default
    assert profile.off_mode == off_mode


@pytest.mark.parametrize("model", ["openai/gpt-5.4", "google/gemini-2.5-flash-lite", ""])
def test_non_claude_models_have_no_profile(model):
    assert claude_thinking_profile(model) is None


def test_haiku_55_direct_is_disabled_without_headroom():
    kwargs = {"model": "claude-haiku-5-5", "max_tokens": 800}
    apply_claude_thinking(
        kwargs,
        claude_thinking_profile("claude-haiku-5-5"),
        enable_thinking=False,
        thinking_tokens=2048,
        via_openrouter=False,
    )
    assert kwargs["thinking"] == {"type": "disabled"}
    assert kwargs["max_tokens"] == 800


def test_haiku_55_via_openrouter_disables_reasoning():
    kwargs = {"model": "openrouter/anthropic/claude-haiku-5.5", "max_tokens": 800}
    apply_claude_thinking(
        kwargs,
        claude_thinking_profile(kwargs["model"]),
        enable_thinking=False,
        thinking_tokens=2048,
        via_openrouter=True,
    )
    assert "thinking" not in kwargs
    assert kwargs["extra_body"]["reasoning"] == {"enabled": False}
    assert kwargs["max_tokens"] == 800


def test_opus_55_cannot_disable_so_gets_low_effort_and_headroom():
    kwargs = {"model": "openrouter/anthropic/claude-opus-5.5", "max_tokens": 800}
    apply_claude_thinking(
        kwargs,
        claude_thinking_profile(kwargs["model"]),
        enable_thinking=False,
        thinking_tokens=2048,
        via_openrouter=True,
    )
    assert kwargs["extra_body"]["reasoning"] == {"effort": "low"}
    assert kwargs["max_tokens"] == 2848


def test_enabled_thinking_uses_adaptive_not_budget_tokens():
    kwargs = {"model": "claude-haiku-5-5", "max_tokens": 2848}
    apply_claude_thinking(
        kwargs,
        claude_thinking_profile("claude-haiku-5-5"),
        enable_thinking=True,
        thinking_tokens=2048,
        via_openrouter=False,
    )
    assert kwargs["thinking"] == {"type": "adaptive"}
    assert kwargs["max_tokens"] == 2848


def _openrouter_router(monkeypatch, llm_settings=None):
    user = User(
        username="tester",
        llm_settings=llm_settings or {},
        encrypted_api_keys={"openrouter": "encrypted-placeholder"},
    )
    monkeypatch.setattr(
        "backend.core.llm_router.GameMasterLLM._get_decrypted_key",
        lambda self, provider: "sk-or-v1-test",
    )
    return GameMasterLLM(user, provider="openrouter")


def test_router_disables_haiku_55_thinking_via_openrouter(monkeypatch):
    router = _openrouter_router(monkeypatch)
    kwargs = {"model": "openrouter/anthropic/claude-haiku-5.5", "max_tokens": 800}
    router._apply_thinking_settings(kwargs)
    assert kwargs["extra_body"]["reasoning"] == {"enabled": False}
    assert "thinking" not in kwargs


def test_router_keeps_budget_tokens_for_legacy_claude(monkeypatch):
    router = _openrouter_router(monkeypatch, {"small_enable_thinking": True})
    kwargs = {"model": "openrouter/anthropic/claude-haiku-4.5", "max_tokens": 800}
    router._apply_thinking_settings(kwargs)
    assert kwargs["thinking"] == {"type": "enabled", "budget_tokens": router.max_thinking_tokens}


def test_router_json_mode_suppresses_default_thinking(monkeypatch):
    router = _openrouter_router(monkeypatch)
    kwargs = {"model": "openrouter/anthropic/claude-haiku-5.5", "max_tokens": 4000}
    router._suppress_default_thinking(kwargs)
    assert kwargs["extra_body"]["reasoning"] == {"enabled": False}
