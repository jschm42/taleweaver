"""Request-level token optimizations for LLM calls (kept out of the oversized llm_router).

- `compact_json_schema`: strips presentation-only keys from a Pydantic JSON schema before
  it is injected into a prompt (JSON-mode fallback providers).
- `apply_prompt_cache_markers`: adds Anthropic `cache_control` breakpoints so the static
  system prompt (and the stable chat history before the latest message) is cached.
  OpenAI, DeepSeek and Gemini cache identical prompt prefixes automatically.
- `bind_llm_session` / `apply_session_cache_routing`: cache routing per game session
  (OpenRouter `session_id`, OpenAI `prompt_cache_key`). For OpenRouter: Without a
  `session_id`, OpenRouter keys stickiness on the first system + first non-system message;
  our first user message carries the volatile CURRENT STATE, so every turn would look like a
  new conversation and could land on a provider endpoint with a cold cache.
"""

from __future__ import annotations

import hashlib
from contextvars import ContextVar
from typing import Any

# Keys that only document the schema; dropping them does not change what is valid.
_SCHEMA_PRESENTATION_KEYS = {"title"}
_CACHE_CONTROL = {"type": "ephemeral"}

# Game session the current request plays in (set once per request by GameTurnManager).
_LLM_SESSION_ID: ContextVar[str | None] = ContextVar("llm_session_id", default=None)


def compact_json_schema(schema: Any) -> Any:
    """Recursively removes presentation-only keys (e.g. `title`) from a JSON schema."""
    if isinstance(schema, list):
        return [compact_json_schema(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    compacted: dict[str, Any] = {}
    for key, value in schema.items():
        # `properties` maps field names to schemas: a field literally named "title" must stay.
        if key == "properties" and isinstance(value, dict):
            compacted[key] = {name: compact_json_schema(sub) for name, sub in value.items()}
            continue
        if key in _SCHEMA_PRESENTATION_KEYS and isinstance(value, str):
            continue
        compacted[key] = compact_json_schema(value)
    return compacted


def supports_explicit_prompt_cache(provider: str, model: str) -> bool:
    """Anthropic models need explicit `cache_control` breakpoints (directly or via OpenRouter)."""
    normalized_model = (model or "").lower()
    if provider == "anthropic":
        return True
    return provider == "openrouter" and (
        "claude" in normalized_model or "anthropic/" in normalized_model
    )


def _mark_message(message: dict[str, Any]) -> None:
    content = message.get("content")
    if isinstance(content, str):
        if not content:
            return
        message["content"] = [{"type": "text", "text": content, "cache_control": _CACHE_CONTROL}]
        return
    if isinstance(content, list) and content and isinstance(content[-1], dict):
        content[-1]["cache_control"] = _CACHE_CONTROL


def apply_prompt_cache_markers(messages: list[dict[str, Any]], provider: str, model: str) -> None:
    """Marks the system prompt and the last message before the final user turn as cacheable.

    Anthropic allows up to 4 breakpoints; prompts below the model's minimum cacheable
    length are simply processed uncached, so marking is always safe.
    """
    if not messages or not supports_explicit_prompt_cache(provider, model):
        return
    if messages[0].get("role") == "system":
        _mark_message(messages[0])
    if len(messages) >= 3:
        _mark_message(messages[-2])


def bind_llm_session(session_id: str | None) -> None:
    """Binds LLM calls of the current request/task to a game session (sticky routing).

    Each request runs in its own context copy, so no reset is needed; background tasks
    started afterwards inherit the binding.
    """
    _LLM_SESSION_ID.set(str(session_id) if session_id else None)


def session_cache_key(model_category: str) -> str | None:
    """Stable, opaque sticky-routing key per game session and model category."""
    session_id = _LLM_SESSION_ID.get()
    if not session_id:
        return None
    digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:32]
    return f"tw-{digest}-{model_category or 'default'}"


def apply_session_cache_routing(
    kwargs: dict[str, Any], provider: str, model_category: str, *, via_openrouter: bool
) -> None:
    """Adds the session's cache-routing key so all calls of a session hit a warm cache.

    - OpenRouter: `session_id` in the body (sticky provider routing).
    - OpenAI: `prompt_cache_key` (routes requests with the same key to the same cache).
    Separate keys per model category: small and complex models are routed independently.
    """
    key = session_cache_key(model_category)
    if not key:
        return
    if via_openrouter:
        extra_body = dict(kwargs.get("extra_body") or {})
        extra_body.setdefault("session_id", key)
        kwargs["extra_body"] = extra_body
        return
    if provider == "openai":
        kwargs.setdefault("prompt_cache_key", key)
