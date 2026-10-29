"""``tw.llm``: lets adventure scripts ask the configured LLM for a short text."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Optional

from backend.engine.scripting.sandbox import in_guard_expression, refund_time_budget

if TYPE_CHECKING:
    from backend.engine.scripting.context import ScriptChangeset

logger = logging.getLogger(__name__)

# (prompt, system prompt, model tier) -> response text. Raises on provider errors.
LlmAsker = Callable[[str, str, str], str]

MODEL_TIERS = ("simple", "advanced")
MAX_CALLS_PER_CONTEXT = 3
MAX_PROMPT_CHARS = 4000
MAX_RESPONSE_CHARS = 2000


class LlmProxy:
    """Safe proxy for LLM calls. Every failure returns an empty string instead of raising."""

    def __init__(
        self,
        asker: Optional[LlmAsker],
        changeset: ScriptChangeset,
        is_debug_enabled: bool = False,
    ):
        self._asker = asker
        self._changeset = changeset
        self._is_debug_enabled = is_debug_enabled
        self._calls = 0

    @property
    def available(self) -> bool:
        """True when this script context may call the LLM (never inside guard expressions)."""
        return self._asker is not None and not in_guard_expression()

    def ask(self, prompt: str, model: str = "simple", system: str = "") -> str:
        """Sends ``prompt`` to the ``simple`` (small) or ``advanced`` (complex) model.

        Returns the answer text, or ``""`` when the LLM is unavailable, the call limit is
        reached, or the request fails or times out.
        """
        tier = str(model or "simple").strip().lower()
        if tier not in MODEL_TIERS:
            raise ValueError(f"tw.llm.ask: model must be 'simple' or 'advanced', got '{model}'.")
        text = str(prompt or "").strip()
        if not text:
            return ""
        if in_guard_expression():
            self._note("tw.llm.ask is not available in guard expressions.")
            return ""
        if self._asker is None:
            self._note("tw.llm.ask is not available in this script context.")
            return ""
        if self._calls >= MAX_CALLS_PER_CONTEXT:
            self._note(f"tw.llm.ask skipped: limit of {MAX_CALLS_PER_CONTEXT} calls reached.")
            return ""
        self._calls += 1
        return self._call(text[:MAX_PROMPT_CHARS], str(system or "")[:MAX_PROMPT_CHARS], tier)

    def _call(self, prompt: str, system: str, tier: str) -> str:
        started = time.monotonic()
        try:
            answer = self._asker(prompt, system, tier) if self._asker else ""
        except Exception as exc:
            logger.warning("[Script] tw.llm.ask (%s) failed: %s", tier, exc)
            self._note(f"tw.llm.ask failed: {exc}")
            return ""
        finally:
            # Waiting for the model must not count against the script's time limit.
            refund_time_budget(time.monotonic() - started)
        return str(answer or "").strip()[:MAX_RESPONSE_CHARS]

    def _note(self, message: str) -> None:
        logger.info("[Script] %s", message)
        if self._is_debug_enabled:
            self._changeset.system_messages.append(f"[DEBUG] {message}")
