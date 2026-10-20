"""Normalization of persisted LLM, TTS and text-to-image user settings.

Older settings payloads used shared keys (`preferred_provider`, `max_tokens`, ...);
these helpers fill per-model keys from those legacy values and apply defaults.
"""

from __future__ import annotations

from typing import Any, Optional

from backend.core.tts_voices import GOOGLE_TTS_VOICE_CATALOG, GOOGLE_TTS_VOICE_LIST

DEFAULT_SMALL_MAX_TOKENS = 12288
DEFAULT_COMPLEX_MAX_TOKENS = 24576
DEFAULT_GENERATOR_MAX_TOKENS = 32768

SUPPORTED_TTS_MODELS = {
    "gemini-3.8-flash-tts",
    "gemini-3.8-flash-lite-tts",
}

TTS_MODEL_ALIASES = {
    # Legacy aliases for backward compatibility
    "gemini-2.5-flash-preview-tts": "gemini-3.8-flash-tts",
    "gemini-2.5-flash-tts-preview": "gemini-3.8-flash-tts",
    "gemini-2.5-flash-tts": "gemini-3.8-flash-tts",
    "gemini-3.1-flash-tts-preview": "gemini-3.8-flash-tts",
}

PLAY_AGENT_PERSONALITIES = ("casual", "bureaucrat", "powerplayer", "custom")
_LEGACY_PERSONALITIES = {"bürokrat": "bureaucrat", "buerokrat": "bureaucrat"}

_LLM_FALLBACK: dict[str, Any] = {
    "small_model": "",
    "small_model_provider": "openai",
    "small_max_tokens": DEFAULT_SMALL_MAX_TOKENS,
    "small_enable_thinking": False,
    "small_max_thinking_tokens": 1024,
    "small_openrouter_provider": "",
    "complex_model": "",
    "complex_model_provider": "openai",
    "complex_max_tokens": DEFAULT_COMPLEX_MAX_TOKENS,
    "complex_enable_thinking": False,
    "complex_max_thinking_tokens": 2048,
    "complex_openrouter_provider": "",
    "generator_model": "",
    "generator_model_provider": "openai",
    "generator_max_tokens": DEFAULT_GENERATOR_MAX_TOKENS,
    "generator_enable_thinking": False,
    "generator_max_thinking_tokens": 2048,
    "generator_openrouter_provider": "",
    "play_agent_model": "",
    "play_agent_model_provider": "openai",
    "play_agent_monkey_mode": False,
    "play_agent_allow_walkthrough": True,
    "play_agent_step_by_step": False,
    "play_agent_openrouter_provider": "",
    "play_agent_personality": "casual",
    "play_agent_custom_personality": "",
    "compression_model": "",
    "compression_model_provider": "openai",
    "compression_max_tokens": 4096,
    "compression_openrouter_provider": "",
    "turns_before_compacting": 10,
    "enable_history_compression": True,
    "preferred_provider": "openai",  # Legacy/Default
    "openrouter_provider": "",
    "ollama_url": "http://localhost:11434",
    "minimax_url": "https://api.minimax.chat/v1",
}

# (key, legacy source keys tried in order, default) for keys missing from stored settings.
# Order matters: later entries may read values filled in by earlier ones.
_LLM_DERIVED_DEFAULTS: tuple[tuple[str, tuple[str, ...], Any], ...] = (
    ("small_model_provider", ("preferred_provider",), "openai"),
    ("complex_model_provider", ("preferred_provider",), "openai"),
    ("generator_model_provider", ("complex_model_provider",), "openai"),
    (
        "play_agent_model_provider",
        ("small_model_provider", "complex_model_provider", "preferred_provider"),
        "openai",
    ),
    ("small_openrouter_provider", ("openrouter_provider",), ""),
    ("complex_openrouter_provider", ("small_openrouter_provider", "openrouter_provider"), ""),
    ("generator_openrouter_provider", ("complex_openrouter_provider", "openrouter_provider"), ""),
    ("play_agent_openrouter_provider", ("small_openrouter_provider", "openrouter_provider"), ""),
    ("openrouter_provider", ("small_openrouter_provider",), ""),
    ("small_max_tokens", ("max_tokens",), DEFAULT_SMALL_MAX_TOKENS),
    ("complex_max_tokens", ("max_tokens",), DEFAULT_COMPLEX_MAX_TOKENS),
    ("generator_max_tokens", ("max_tokens",), DEFAULT_GENERATOR_MAX_TOKENS),
    ("small_enable_thinking", ("enable_thinking",), False),
    ("small_max_thinking_tokens", ("max_thinking_tokens",), 1024),
    ("complex_enable_thinking", ("enable_thinking",), False),
    ("complex_max_thinking_tokens", ("max_thinking_tokens",), 1024),
    ("generator_enable_thinking", ("enable_thinking",), False),
    ("generator_max_thinking_tokens", ("max_thinking_tokens",), 1024),
)

# Compression defaults depend on the small model after the small/complex fallback.
_COMPRESSION_DERIVED_DEFAULTS: tuple[tuple[str, tuple[str, ...], Any], ...] = (
    ("compression_model_provider", ("small_model_provider",), "openai"),
    ("compression_openrouter_provider", ("small_openrouter_provider",), ""),
    ("compression_max_tokens", (), 4096),
    ("compression_model", (), ""),
)

_FULL_MODEL_FIELDS = (
    "model",
    "model_provider",
    "max_tokens",
    "enable_thinking",
    "max_thinking_tokens",
)
_OPENROUTER_MODEL_PREFIXES = ("small", "complex", "generator", "play_agent", "compression")


def normalize_openrouter_model(model: Optional[str]) -> Optional[str]:
    """Strip provider prefixes from models stored for OpenRouter."""
    if not isinstance(model, str):
        return model

    normalized = model.strip()
    if not normalized:
        return normalized

    if normalized.lower().startswith("openrouter/"):
        return normalized[len("openrouter/") :].strip()

    return normalized


def _apply_derived_defaults(
    normalized: dict[str, Any], rules: tuple[tuple[str, tuple[str, ...], Any], ...]
) -> None:
    for key, sources, default in rules:
        if key in normalized:
            continue
        values = (normalized.get(source) for source in sources)
        normalized[key] = next((value for value in values if value), default)


def _copy_model_fields(
    normalized: dict[str, Any], source: str, target: str, fields: tuple[str, ...]
) -> None:
    for field in fields:
        normalized[f"{target}_{field}"] = normalized.get(f"{source}_{field}")


def _apply_model_fallbacks(normalized: dict[str, Any]) -> None:
    """Fills missing small/complex/generator/play-agent models from their siblings."""
    small_model = normalized.get("small_model")
    complex_model = normalized.get("complex_model")
    if small_model and not complex_model:
        _copy_model_fields(normalized, "small", "complex", _FULL_MODEL_FIELDS)
    elif complex_model and not small_model:
        # The small model keeps its own thinking budget.
        _copy_model_fields(normalized, "complex", "small", _FULL_MODEL_FIELDS[:4])

    if not normalized.get("generator_model") and normalized.get("complex_model"):
        _copy_model_fields(normalized, "complex", "generator", _FULL_MODEL_FIELDS)

    if not normalized.get("play_agent_model") and normalized.get("small_model"):
        _copy_model_fields(normalized, "small", "play_agent", ("model", "model_provider"))


def _normalize_personality(value: Any) -> str:
    if not value:
        return "casual"
    personality = str(value).strip().lower()
    personality = _LEGACY_PERSONALITIES.get(personality, personality)
    return personality if personality in PLAY_AGENT_PERSONALITIES else "casual"


def _apply_play_agent_options(normalized: dict[str, Any]) -> None:
    normalized.setdefault("play_agent_monkey_mode", False)
    normalized["play_agent_allow_walkthrough"] = bool(
        normalized.get("play_agent_allow_walkthrough", True)
    )
    normalized["play_agent_step_by_step"] = bool(normalized.get("play_agent_step_by_step", False))
    normalized["play_agent_personality"] = _normalize_personality(
        normalized.get("play_agent_personality")
    )
    normalized["play_agent_custom_personality"] = str(
        normalized.get("play_agent_custom_personality", "")
    )


def _apply_history_options(normalized: dict[str, Any]) -> None:
    if "turns_before_compacting" not in normalized:
        normalized["turns_before_compacting"] = normalized.get("default_max_memory_turns", 10)
    try:
        turns = int(normalized["turns_before_compacting"])
        normalized["turns_before_compacting"] = max(1, min(100, turns))
    except (ValueError, TypeError):
        normalized["turns_before_compacting"] = 10

    if "enable_history_compression" not in normalized:
        normalized["enable_history_compression"] = normalized.get("enable_compacting", True)
    normalized["enable_history_compression"] = bool(normalized["enable_history_compression"])


def _apply_openrouter_models(normalized: dict[str, Any], prefixes: tuple[str, ...]) -> None:
    for prefix in prefixes:
        if normalized.get(f"{prefix}_model_provider") == "openrouter":
            model_key = f"{prefix}_model"
            normalized[model_key] = normalize_openrouter_model(normalized.get(model_key))


def normalize_llm_settings(llm_settings: Optional[dict]) -> dict:
    """Return LLM settings with separate providers, tokens and thinking modes."""
    if not llm_settings:
        return dict(_LLM_FALLBACK)

    normalized = dict(llm_settings)
    _apply_derived_defaults(normalized, _LLM_DERIVED_DEFAULTS)
    _apply_model_fallbacks(normalized)
    _apply_play_agent_options(normalized)
    _apply_derived_defaults(normalized, _COMPRESSION_DERIVED_DEFAULTS)
    _apply_history_options(normalized)
    _apply_openrouter_models(normalized, _OPENROUTER_MODEL_PREFIXES)
    return normalized


def _tts_fallback() -> dict[str, Any]:
    return {
        "enabled": False,
        "provider": "google",
        "selected_model": "gemini-3.8-flash-tts",
        "voice_list": list(GOOGLE_TTS_VOICE_LIST),
        "voice_catalog": [dict(entry) for entry in GOOGLE_TTS_VOICE_CATALOG],
        "selected_voice": "Puck",
        "elevenlabs_voice_id": "",
        "use_vocal_tags": True,
        "use_text_chunking": True,
        "use_streaming": False,
        "speech_rate": 1.0,
    }


def _apply_legacy_tts_model(normalized: dict[str, Any]) -> None:
    """Accepts historical/alternate model keys to avoid silently resetting the selection."""
    if "selected_model" not in normalized:
        legacy_keys = ("model", "tts_model", "single_voice_model", "single_voice_tts_model")
        legacy = next((normalized.get(k) for k in legacy_keys if normalized.get(k)), None)
        if legacy:
            normalized["selected_model"] = legacy

    selected_model = str(normalized.get("selected_model") or "").strip()
    if selected_model in TTS_MODEL_ALIASES:
        normalized["selected_model"] = TTS_MODEL_ALIASES[selected_model]


def normalize_tts_settings(tts_settings: Optional[dict]) -> dict:
    """Return TTS settings with voice list, selected voice and style context."""
    fallback = _tts_fallback()
    if not tts_settings:
        return fallback

    normalized = dict(tts_settings)
    _apply_legacy_tts_model(normalized)
    normalized["provider"] = normalized.get("provider") or "google"
    normalized["elevenlabs_voice_id"] = normalized.get("elevenlabs_voice_id", "")

    # Only fill flags that are missing entirely; explicit False values must survive.
    for key in ("use_vocal_tags", "use_text_chunking", "use_streaming", "enabled"):
        normalized.setdefault(key, fallback[key])

    unsupported_google_model = (
        normalized.get("provider") == "google"
        and normalized.get("selected_model") not in SUPPORTED_TTS_MODELS
    )
    if "selected_model" not in normalized or unsupported_google_model:
        normalized["selected_model"] = fallback["selected_model"]

    # Always ensure the full list is available
    normalized["voice_list"] = fallback["voice_list"]
    normalized["voice_catalog"] = fallback["voice_catalog"]
    normalized.setdefault("selected_voice", fallback["selected_voice"])
    normalized.setdefault("speech_rate", fallback["speech_rate"])
    return normalized


_T2I_FALLBACK: dict[str, Any] = {
    "simple_model": "",
    "simple_model_provider": "openai",
    "advanced_model": "",
    "advanced_model_provider": "openai",
    "provider": "openai",  # Legacy/Default
    "ollama_url": "http://localhost:11434",
    "stable_diffusion_url": "http://127.0.0.1:7860",
    "width": None,
    "height": None,
    "steps": None,
    "cfg_scale": None,
    "simple_steps": None,
    "simple_cfg_scale": None,
    "advanced_steps": None,
    "advanced_cfg_scale": None,
    "simple_sampler_name": None,
    "simple_scheduler": None,
    "advanced_sampler_name": None,
    "advanced_scheduler": None,
    "simple_min_long_edge": None,
    "advanced_min_long_edge": None,
    "seed": None,
    "image_format": "jpeg",
    "image_quality": 85,
    "negative_prompt": None,
    # Model usage quality per content type
    "scene_model_quality": "advanced",
    "profile_model_quality": "advanced",
    "protagonist_model_quality": "advanced",
    "asset_model_quality": "simple",
}

_T2I_DERIVED_DEFAULTS: tuple[tuple[str, tuple[str, ...], Any], ...] = (
    ("simple_model_provider", ("provider",), "openai"),
    ("advanced_model_provider", ("provider",), "openai"),
)

# Keys filled with their fallback value when missing from stored settings.
_T2I_STATIC_DEFAULT_KEYS = (
    "stable_diffusion_url",
    "ollama_url",
    "cfg_scale",
    "simple_steps",
    "simple_cfg_scale",
    "advanced_steps",
    "advanced_cfg_scale",
    "simple_sampler_name",
    "simple_scheduler",
    "advanced_sampler_name",
    "advanced_scheduler",
    "simple_min_long_edge",
    "advanced_min_long_edge",
    "scene_model_quality",
    "profile_model_quality",
    "protagonist_model_quality",
    "asset_model_quality",
)


def normalize_t2i_settings(t2i_settings: Optional[dict]) -> dict:
    """Return T2I settings with separate providers."""
    if not t2i_settings:
        return dict(_T2I_FALLBACK)

    normalized = dict(t2i_settings)
    _apply_derived_defaults(normalized, _T2I_DERIVED_DEFAULTS)
    for key in _T2I_STATIC_DEFAULT_KEYS:
        normalized.setdefault(key, _T2I_FALLBACK[key])
    _apply_openrouter_models(normalized, ("simple", "advanced"))
    return normalized
