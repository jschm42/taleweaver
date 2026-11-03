"""``tw.llm`` and ``tw.json``: lets adventure scripts ask the LLM for text or validated JSON."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Optional

from backend.engine.scripting.json_validator import (
    parse_llm_json,
    schema_prompt_hint,
    validate_json_schema,
)
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
MAX_JSON_RESPONSE_CHARS = 8000
DEFAULT_JSON_SYSTEM_PROMPT = (
    "You generate structured JSON for an interactive adventure. "
    "Return ONLY valid JSON without markdown code fences or explanations."
)


class JsonProxy:
    """Safe sandbox proxy exposed as ``tw.json`` for parsing, validating, and dumping JSON."""

    def __init__(self, changeset: ScriptChangeset, is_debug_enabled: bool = False):
        self._changeset = changeset
        self._is_debug_enabled = is_debug_enabled

    def loads(self, text: str, schema: Any = None, default: Any = None) -> Any:
        """Parses ``text`` as JSON and optionally validates it against ``schema``.

        Returns ``default`` (``None``) when parsing or schema validation fails.
        """
        raw = str(text or "").strip()
        if not raw:
            return default
        data, parse_err = parse_llm_json(raw[:MAX_JSON_RESPONSE_CHARS])
        if parse_err is not None:
            self._note(f"tw.json.loads failed: {parse_err}.")
            return default
        schema_err = validate_json_schema(data, schema)
        if schema_err is not None:
            self._note(f"tw.json.loads schema mismatch: {schema_err}.")
            return default
        return data

    def validate(self, data: Any, schema: Any) -> bool:
        """Returns True when ``data`` matches ``schema``."""
        return validate_json_schema(data, schema) is None

    def dumps(self, value: Any) -> str:
        """Serializes ``value`` to a JSON string (or ``""`` if not JSON-serializable)."""
        try:
            return json.dumps(value, ensure_ascii=False)[:MAX_JSON_RESPONSE_CHARS]
        except Exception as exc:
            self._note(f"tw.json.dumps failed: {exc}")
            return ""

    def _note(self, message: str) -> None:
        logger.info("[Script] %s", message)
        if self._is_debug_enabled:
            self._changeset.system_messages.append(f"[DEBUG] {message}")


class LlmProxy:
    """Safe proxy for LLM calls. Every failure returns an empty string / None instead of raising."""

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
        raw = self._request_raw("tw.llm.ask", prompt, model, system, MAX_RESPONSE_CHARS)
        return raw if raw is not None else ""

    def ask_json(
        self,
        prompt: str,
        schema: Any = None,
        model: str = "simple",
        system: str = "",
    ) -> Any:
        """Asks the model for JSON and validates it against ``schema`` (if given).

        Returns the parsed ``dict`` / ``list`` (or primitive when requested by ``schema``),
        or ``None`` when the LLM is unavailable, the call limit is reached, the response is
        not valid JSON, or ``schema`` validation fails.
        """
        base_system = str(system or "").strip() or DEFAULT_JSON_SYSTEM_PROMPT
        full_system = f"{base_system}\n{schema_prompt_hint(schema)}"
        raw = self._request_raw(
            "tw.llm.ask_json", prompt, model, full_system, MAX_JSON_RESPONSE_CHARS
        )
        if not raw:
            return None
        data, parse_err = parse_llm_json(raw)
        if parse_err is not None:
            self._note(f"tw.llm.ask_json failed: {parse_err}.")
            return None
        if schema is None and not isinstance(data, (dict, list)):
            self._note(
                f"tw.llm.ask_json failed: expected JSON object or array, got {type(data).__name__}."
            )
            return None
        schema_err = validate_json_schema(data, schema)
        if schema_err is not None:
            self._note(f"tw.llm.ask_json schema validation failed: {schema_err}.")
            return None
        return data

    def _request_raw(
        self,
        caller: str,
        prompt: str,
        model: str,
        system: str,
        max_chars: int,
    ) -> Optional[str]:
        tier = str(model or "simple").strip().lower()
        if tier not in MODEL_TIERS:
            raise ValueError(f"{caller}: model must be 'simple' or 'advanced', got '{model}'.")
        text = str(prompt or "").strip()
        if not text:
            return None
        if in_guard_expression():
            self._note(f"{caller} is not available in guard expressions.")
            return None
        if self._asker is None:
            self._note(f"{caller} is not available in this script context.")
            return None
        if self._calls >= MAX_CALLS_PER_CONTEXT:
            self._note(f"{caller} skipped: limit of {MAX_CALLS_PER_CONTEXT} calls reached.")
            return None
        self._calls += 1
        return self._call(
            caller,
            text[:MAX_PROMPT_CHARS],
            str(system or "")[:MAX_PROMPT_CHARS],
            tier,
            max_chars,
        )

    def _call(
        self, caller: str, prompt: str, system: str, tier: str, max_chars: int
    ) -> Optional[str]:
        started = time.monotonic()
        try:
            answer = self._asker(prompt, system, tier) if self._asker else ""
        except Exception as exc:
            logger.warning("[Script] %s (%s) failed: %s", caller, tier, exc)
            self._note(f"{caller} failed: {exc}")
            return None
        finally:
            # Waiting for the model must not count against the script's time limit.
            refund_time_budget(time.monotonic() - started)
        result = str(answer or "").strip()[:max_chars]
        return result or None

    def _note(self, message: str) -> None:
        logger.info("[Script] %s", message)
        if self._is_debug_enabled:
            self._changeset.system_messages.append(f"[DEBUG] {message}")
