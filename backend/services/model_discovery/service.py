"""Model discovery: provider registry, caching and fallback to the built-in lists.

The UI always gets a usable list: live models when the provider answers, otherwise the
built-in defaults together with the reason the live list is missing.
"""

import time
from dataclasses import dataclass
from typing import Literal, Optional

import httpx

from backend.core.models_config import (
    IMAGE_PROVIDERS,
    LLM_PROVIDERS,
    PREDEFINED_IMAGE_MODELS,
    PREDEFINED_LLM_MODELS,
)
from backend.services.model_discovery import fetchers
from backend.services.model_discovery.classify import IMAGE, LLM, ModelKind
from backend.services.model_discovery.fetchers import DiscoveredModel, DiscoveryError, Fetcher

CACHE_TTL_SECONDS = 600
_FETCH_TIMEOUT = 15.0

Source = Literal["live", "static", "fallback"]


@dataclass(frozen=True)
class ProviderSpec:
    fetch: Optional[Fetcher]
    default_base: str = ""
    needs_key: bool = True
    # Only self-hosted endpoints may be redirected; key-bearing requests never go to
    # a caller-supplied host.
    custom_base: bool = False


PROVIDERS: dict[str, ProviderSpec] = {
    "custom_openai": ProviderSpec(
        fetchers.fetch_openai_compatible, "", needs_key=False, custom_base=True
    ),
    "openai": ProviderSpec(fetchers.fetch_openai, "https://api.openai.com/v1"),
    "anthropic": ProviderSpec(fetchers.fetch_anthropic, "https://api.anthropic.com/v1"),
    "google": ProviderSpec(
        fetchers.fetch_google, "https://generativelanguage.googleapis.com/v1beta"
    ),
    "openrouter": ProviderSpec(
        fetchers.fetch_openrouter, "https://openrouter.ai/api/v1", needs_key=False
    ),
    "deepseek": ProviderSpec(fetchers.fetch_openai_compatible, "https://api.deepseek.com/v1"),
    "kimi": ProviderSpec(fetchers.fetch_openai_compatible, "https://api.moonshot.ai/v1"),
    "minimax": ProviderSpec(
        fetchers.fetch_openai_compatible, "https://api.minimax.chat/v1", custom_base=True
    ),
    "ollama": ProviderSpec(
        fetchers.fetch_ollama, "http://localhost:11434", needs_key=False, custom_base=True
    ),
    "comfyui": ProviderSpec(
        fetchers.fetch_comfyui, "http://127.0.0.1:8188", needs_key=False, custom_base=True
    ),
    "stable_diffusion": ProviderSpec(
        fetchers.fetch_stable_diffusion, "http://127.0.0.1:7860", needs_key=False, custom_base=True
    ),
    # Black Forest Labs has no listing endpoint; the built-in list is authoritative.
    "black_forest_labs": ProviderSpec(fetch=None),
}

_KIND_PROVIDERS: dict[str, set[str]] = {
    "llm": {p["id"] for p in LLM_PROVIDERS},
    "image": {p["id"] for p in IMAGE_PROVIDERS},
}
_STATIC_LISTS: dict[str, dict[str, list[str]]] = {
    "llm": PREDEFINED_LLM_MODELS,
    "image": PREDEFINED_IMAGE_MODELS,
}

# Display names for providers without a listing API.
STATIC_MODEL_LABELS: dict[str, dict[str, str]] = {
    "black_forest_labs": {
        "flux-3-image": "FLUX 3 Image",
        "flux-3-image-klein": "FLUX 3 Image Klein",
        "flux-2-klein-4b": "FLUX.2 [klein] 4B",
        "flux-2-klein-9b": "FLUX.2 [klein] 9B",
        "flux-2-flex": "FLUX.2 [flex]",
        "flux-2-pro": "FLUX.2 [pro]",
        "flux-2-max": "FLUX.2 [max]",
        "flux-dev": "FLUX.1 [dev]",
        "flux-pro": "FLUX.1 [pro]",
        "flux-pro-1.1": "FLUX1.1 [pro]",
    },
}

_cache: dict[tuple[str, str], tuple[float, list[DiscoveredModel]]] = {}


@dataclass(frozen=True)
class DiscoveryResult:
    models: list[DiscoveredModel]
    source: Source
    error: Optional[str] = None


def supports_kind(provider: str, kind: ModelKind) -> bool:
    return provider in _KIND_PROVIDERS[kind]


def supports_custom_base(provider: str) -> bool:
    spec = PROVIDERS.get(provider)
    return bool(spec and spec.custom_base)


def clear_cache() -> None:
    _cache.clear()


def _static_models(provider: str, kind: ModelKind) -> list[DiscoveredModel]:
    kinds = LLM if kind == "llm" else IMAGE
    labels = STATIC_MODEL_LABELS.get(provider, {})
    return [
        DiscoveredModel(id=m, label=labels.get(m, m), kinds=kinds)
        for m in _STATIC_LISTS[kind].get(provider, [])
    ]


def _cache_key(provider: str, base_url: str) -> tuple[str, str]:
    return provider, base_url


async def _fetch(
    spec: ProviderSpec, api_key: Optional[str], base_url: str, client: Optional[httpx.AsyncClient]
) -> list[DiscoveredModel]:
    if client is not None:
        return await spec.fetch(client, api_key, base_url)
    async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT) as own_client:
        return await spec.fetch(own_client, api_key, base_url)


async def _cached_fetch(
    provider: str,
    spec: ProviderSpec,
    api_key: Optional[str],
    base_url: str,
    refresh: bool,
    client: Optional[httpx.AsyncClient],
) -> list[DiscoveredModel]:
    key = _cache_key(provider, base_url)
    cached = _cache.get(key)
    if cached and not refresh and time.monotonic() - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]
    models = await _fetch(spec, api_key, base_url, client)
    _cache[key] = (time.monotonic(), models)
    return models


async def discover_models(
    provider: str,
    kind: ModelKind,
    api_key: Optional[str],
    base_url: Optional[str] = None,
    refresh: bool = False,
    client: Optional[httpx.AsyncClient] = None,
) -> DiscoveryResult:
    """Return the provider's models for `kind`, live when possible."""
    spec = PROVIDERS.get(provider)
    if spec is None or spec.fetch is None:
        return DiscoveryResult(_static_models(provider, kind), "static")
    if spec.needs_key and not api_key:
        return DiscoveryResult(_static_models(provider, kind), "fallback", "No API key configured.")

    target = (base_url if spec.custom_base and base_url else spec.default_base).rstrip("/")
    if not target:
        return DiscoveryResult(
            _static_models(provider, kind), "fallback", "Configure a Base URL first."
        )
    try:
        models = await _cached_fetch(provider, spec, api_key, target, refresh, client)
    except DiscoveryError as exc:
        return DiscoveryResult(_static_models(provider, kind), "fallback", str(exc))

    matching = sorted((m for m in models if kind in m.kinds), key=lambda m: m.id.lower())
    return DiscoveryResult(matching, "live")
