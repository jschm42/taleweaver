"""Thinking request parameters for Claude models (direct Anthropic or via OpenRouter).

Claude models from the 5.x generation think by default, even without a `thinking`
parameter, and reject `{"type": "enabled", "budget_tokens": N}` with a 400. Their thinking
tokens count against `max_tokens`: with a narration cap of 600-2000 tokens the model can use
the whole budget for thinking and return no visible text. These models therefore get an
explicit off switch where one exists, and extra `max_tokens` headroom where none exists.

Older models (Haiku 4.5, Sonnet/Opus 4.6 and earlier) keep the `budget_tokens` form.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_DISABLED: dict[str, str] = {"type": "disabled"}
_BETWEEN_TOOLS: dict[str, str] = {"type": "between_tools"}

# claude-haiku-5-5, anthropic/claude-haiku-5.5, claude-sonnet-4-20250514 (minor: max 2 digits)
_CLAUDE_MODEL = re.compile(r"claude-(haiku|sonnet|opus|fable|mythos)-(\d+)(?:[.-](\d{1,2}))?(?!\d)")


@dataclass(frozen=True)
class ClaudeThinkingProfile:
    # Accepts {"type": "enabled", "budget_tokens": N} (pre-5.x models).
    budget_tokens: bool
    # Thinks without any thinking parameter.
    on_by_default: bool
    # `thinking` value that turns thinking off, or None if it cannot be turned off.
    off_mode: dict[str, str] | None


_LEGACY = ClaudeThinkingProfile(budget_tokens=True, on_by_default=False, off_mode=None)
_ALWAYS_ON = ClaudeThinkingProfile(budget_tokens=False, on_by_default=True, off_mode=None)

# Per family: (minimum version, profile), newest first. Older versions fall back to _LEGACY.
_PROFILES: dict[str, list[tuple[tuple[int, int], ClaudeThinkingProfile]]] = {
    "fable": [((0, 0), _ALWAYS_ON)],
    "mythos": [((0, 0), _ALWAYS_ON)],
    "haiku": [((5, 5), ClaudeThinkingProfile(False, True, _DISABLED))],
    "sonnet": [
        ((5, 5), ClaudeThinkingProfile(False, True, _BETWEEN_TOOLS)),
        ((5, 0), ClaudeThinkingProfile(False, True, _DISABLED)),
    ],
    "opus": [
        ((5, 5), _ALWAYS_ON),
        ((5, 0), ClaudeThinkingProfile(False, True, _DISABLED)),
        ((4, 7), ClaudeThinkingProfile(False, False, _DISABLED)),
    ],
}


def claude_thinking_profile(model: str) -> ClaudeThinkingProfile | None:
    """Thinking rules for a Claude model slug, or None for non-Claude models."""
    match = _CLAUDE_MODEL.search((model or "").lower())
    if not match:
        return None
    version = (int(match.group(2)), int(match.group(3) or 0))
    for min_version, profile in _PROFILES[match.group(1)]:
        if version >= min_version:
            return profile
    return _LEGACY


def apply_claude_thinking(
    kwargs: dict[str, Any],
    profile: ClaudeThinkingProfile,
    *,
    enable_thinking: bool,
    thinking_tokens: int,
    via_openrouter: bool,
) -> None:
    """Sets thinking for a model without `budget_tokens` support (profile.budget_tokens False).

    Callers already add `thinking_tokens` to `max_tokens` when thinking is enabled. When the
    model thinks although it is disabled (no off switch), the headroom is added here.
    """
    if via_openrouter:
        # LiteLLM drops `thinking` for models it does not know (drop_params=True), so use
        # OpenRouter's own reasoning field.
        if enable_thinking:
            reasoning: dict[str, Any] = {"enabled": True}
        elif profile.off_mode == _DISABLED:
            reasoning = {"enabled": False}
        else:
            # No plain off switch: keep thinking as short as possible.
            reasoning = {"effort": "low"}
        extra_body = dict(kwargs.get("extra_body") or {})
        extra_body["reasoning"] = reasoning
        kwargs["extra_body"] = extra_body
    elif enable_thinking:
        kwargs["thinking"] = {"type": "adaptive"}
    elif profile.off_mode is not None:
        kwargs["thinking"] = dict(profile.off_mode)

    # Sonnet 5.5's between_tools still thinks between tool calls, but narration has no tools.
    can_turn_off = profile.off_mode is not None and (
        via_openrouter is False or profile.off_mode == _DISABLED
    )
    if not enable_thinking and profile.on_by_default and not can_turn_off:
        kwargs["max_tokens"] = int(kwargs.get("max_tokens") or 0) + thinking_tokens
