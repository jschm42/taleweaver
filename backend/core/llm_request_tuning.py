"""Request-level token optimizations for LLM calls (kept out of the oversized llm_router).

- `compact_json_schema`: strips presentation-only keys from a Pydantic JSON schema before
  it is injected into a prompt (JSON-mode fallback providers).
- `apply_prompt_cache_markers`: adds Anthropic `cache_control` breakpoints so the static
  system prompt (and the stable chat history before the latest message) is cached.
  OpenAI, DeepSeek and Gemini cache identical prompt prefixes automatically.
"""

from __future__ import annotations

from typing import Any

# Keys that only document the schema; dropping them does not change what is valid.
_SCHEMA_PRESENTATION_KEYS = {"title"}
_CACHE_CONTROL = {"type": "ephemeral"}


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
