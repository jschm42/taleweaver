"""Provider-specific request configuration for LiteLLM calls (model slugs, endpoints, JSON mode)."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from backend.core.llm_request_tuning import compact_json_schema

OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"
# OpenAI-compatible providers whose keys may also start with "sk-or-v1" and must never be
# auto-routed to OpenRouter.
OPENAI_COMPATIBLE_PROVIDERS = ("kimi", "minimax", "deepseek", "custom_openai")

# provider -> (custom_llm_provider, fixed api_base)
_FIXED_ENDPOINTS: dict[str, tuple[str, str | None]] = {
    "openrouter": ("openrouter", None),
    "openai": ("openai", None),
    "anthropic": ("anthropic", "https://api.anthropic.com"),
    "deepseek": ("deepseek", "https://api.deepseek.com"),
}

# Bare OpenRouter model ids need a vendor prefix (e.g. gpt-4o-mini -> openai/gpt-4o-mini).
_OPENROUTER_VENDOR_PREFIXES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("gpt-", "o1", "o3", "o4", "text-", "chatgpt-"), "openai"),
    (("claude-",), "anthropic"),
    (("gemini-",), "google"),
    (("deepseek-",), "deepseek"),
    (("mistral-", "mixtral-"), "mistralai"),
    (("llama-", "meta-"), "meta-llama"),
    (("qwen-",), "qwen"),
)

JSON_SCHEMA_INSTRUCTION = (
    "\n\nCRITICAL: You MUST respond with a single JSON object matching this schema exactly.\n"
    "DO NOT wrap the response in a list (no square brackets at the top level).\n"
    "DO NOT include any markdown formatting or text outside the JSON.\n"
    "CRITICAL: Do NOT translate the JSON key names. The JSON keys MUST be exactly identical to the schema keys in English.\n"
    "SCHEMA:\n{schema_json}"
)


def _strip_wrapper_prefix(model: str, wrapper: str) -> str:
    if model.lower().startswith(f"{wrapper}/"):
        return model.split("/", 1)[1].strip()
    return model


def _normalize_gemini(model: str) -> str:
    # LiteLLM expects 'gemini/...' for Google Gemini models.
    return model if model.startswith("gemini/") else f"gemini/{model}"


def _normalize_openrouter(model: str) -> str:
    # OpenRouter model ids often require provider prefixes; only strip an optional
    # leading openrouter/ wrapper.
    model = _strip_wrapper_prefix(model, "openrouter")
    if "/" in model:
        return model
    vendor = next(
        (vendor for prefixes, vendor in _OPENROUTER_VENDOR_PREFIXES if model.startswith(prefixes)),
        None,
    )
    return f"{vendor}/{model}" if vendor else model


def _normalize_anthropic(model: str) -> str:
    # Ensure Anthropic requests cannot be misrouted through OpenAI-compatible defaults.
    return model if model.startswith("anthropic/") else f"anthropic/{model}"


def _normalize_default(model: str) -> str:
    return model.split("/", 1)[1].strip() if "/" in model else model


_MODEL_NORMALIZERS = {
    "ollama": lambda model: model,
    # LiteLLM removes one adapter prefix; always add it so raw vendor/openai slashes survive.
    "custom_openai": lambda model: f"openai/{model}",
    "google": _normalize_gemini,
    "gemini": _normalize_gemini,
    "openrouter": _normalize_openrouter,
    "anthropic": _normalize_anthropic,
    # Kimi (Moonshot) and MiniMax use OpenAI-compatible endpoints with raw model ids.
    "kimi": lambda model: _strip_wrapper_prefix(model, "kimi"),
    "minimax": lambda model: _strip_wrapper_prefix(model, "minimax"),
}


def normalize_model(provider: str, model: str) -> str:
    """Returns a LiteLLM-friendly model slug for the configured provider."""
    normalized = (model or "").strip()
    if not normalized:
        raise ValueError(f"No model configured for provider '{provider}'.")
    return _MODEL_NORMALIZERS.get(provider, _normalize_default)(normalized)


def apply_provider_endpoint(
    kwargs: dict[str, Any],
    *,
    provider: str,
    api_key: str | None,
    api_base: str | None,
    kimi_api_base: str,
    minimax_api_base: str,
) -> None:
    """Sets api_key/api_base/custom_llm_provider for a non-streaming or streaming request."""
    if provider == "ollama":
        kwargs["api_base"] = api_base
        kwargs["custom_llm_provider"] = "ollama"
        return

    if provider == "custom_openai":
        if not api_base:
            raise ValueError("Configure an OpenAI-compatible Base URL first.")
        kwargs.update(
            api_base=api_base, api_key=api_key or "local-no-key", custom_llm_provider="openai"
        )
        return

    kwargs["api_key"] = api_key
    endpoints = {
        **_FIXED_ENDPOINTS,
        "kimi": ("openai", kimi_api_base),
        "minimax": ("openai", minimax_api_base),
    }
    custom_provider, fixed_base = endpoints.get(provider, (None, None))
    if custom_provider:
        kwargs["custom_llm_provider"] = custom_provider
    if fixed_base:
        kwargs["api_base"] = fixed_base

    # Auto-detect OpenRouter keys (only when no other OpenAI-compatible provider is set).
    is_openrouter_key = str(api_key or "").startswith("sk-or-v1")
    if provider not in OPENAI_COMPATIBLE_PROVIDERS and (
        is_openrouter_key or provider == "openrouter"
    ):
        kwargs["api_base"] = OPENROUTER_API_BASE


def is_minimax_model(provider: str, normalized_model: str) -> bool:
    return "minimax" in normalized_model.lower() or provider == "minimax"


def uses_json_mode_fallback(provider: str, normalized_model: str) -> bool:
    """Whether structured output must use prompt-injected JSON mode instead of a schema.

    Anthropic (24-optional-parameter grammar limit), DeepSeek, Kimi, MiniMax and OpenRouter
    often fail with complex Pydantic schemas. Direct Gemini supports response_schema. Only an
    explicit openrouter provider counts: key-prefix detection would falsely match other keys.
    """
    model = normalized_model.lower()
    return (
        "claude" in model
        or provider == "anthropic"
        or "deepseek" in model
        or provider == "deepseek"
        or "kimi" in model
        or "moonshot" in model
        or provider == "kimi"
        or is_minimax_model(provider, normalized_model)
        or provider in ("openrouter", "custom_openai")
    )


def json_schema_instruction(response_model: type[BaseModel]) -> str:
    """Schema instruction appended to the system prompt in JSON-mode fallback."""
    schema_json = json.dumps(
        compact_json_schema(response_model.model_json_schema()), separators=(",", ":")
    )
    return JSON_SCHEMA_INSTRUCTION.format(schema_json=schema_json)
