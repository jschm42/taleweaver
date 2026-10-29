"""Builds the LLM callback behind ``tw.llm.ask`` for adventure scripts.

Scripts run synchronously inside the sandbox, so the call blocks the script (and the request
handling it) until the model answers or ``SCRIPT_LLM_TIMEOUT_SECONDS`` passes. The request runs
in a worker thread so a hanging provider can be abandoned after the timeout.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

from backend.core.llm_router import GameMasterLLM
from backend.engine.scripting.llm_proxy import LlmAsker

logger = logging.getLogger(__name__)

SCRIPT_LLM_TIMEOUT_SECONDS = 20
SCRIPT_LLM_MAX_TOKENS = 600
DEFAULT_SYSTEM_PROMPT = (
    "You help run an interactive text adventure. Answer briefly and return only the "
    "requested text, without explanations or formatting."
)

_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="script-llm")


def _model_for(user: Any, tier: str) -> tuple[str, str, str]:
    """Returns (provider, model, router category) for ``simple`` or ``advanced``."""
    settings = getattr(user, "llm_settings", None) or {}
    fallback_provider = settings.get("preferred_provider") or "openai"
    if tier == "advanced":
        provider = (
            settings.get("complex_model_provider")
            or settings.get("small_model_provider")
            or fallback_provider
        )
        return provider, settings.get("complex_model") or "gpt-4o", "complex"
    provider = settings.get("small_model_provider") or fallback_provider
    return provider, settings.get("small_model") or "gpt-4o-mini", "small"


def make_script_llm_asker(
    user: Any,
    *,
    game_id: Optional[str] = None,
    adventure_id: Optional[str] = None,
    language: Optional[str] = None,
) -> LlmAsker:
    """Returns the callback ``tw.llm.ask`` uses for this user and session."""

    def ask(prompt: str, system: str, tier: str) -> str:
        provider, model, category = _model_for(user, tier)
        llm = GameMasterLLM(user, provider=provider, model_category=category)
        llm.max_tokens = min(int(llm.max_tokens or SCRIPT_LLM_MAX_TOKENS), SCRIPT_LLM_MAX_TOKENS)
        system_prompt = system or DEFAULT_SYSTEM_PROMPT
        if language:
            system_prompt += f" Respond only in {language.upper()}."
        future = _EXECUTOR.submit(
            llm.execute_simple_task,
            system_prompt,
            prompt,
            model,
            adventure_id=adventure_id,
            game_id=game_id,
            operation="script.llm_ask",
            phase=tier,
        )
        return str(future.result(timeout=SCRIPT_LLM_TIMEOUT_SECONDS) or "")

    return ask
