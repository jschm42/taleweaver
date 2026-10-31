"""Per-provider model list adapters.

Each adapter calls the provider's own listing endpoint with the provider's own auth
scheme and returns `DiscoveredModel`s tagged with the roles they can serve. Failures
raise `DiscoveryError` with a message that is safe to show in the admin UI.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from backend.services.model_discovery.classify import (
    IMAGE,
    LLM,
    LLM_AND_IMAGE,
    Kinds,
    classify_google,
    classify_openai,
    classify_openrouter,
)

ANTHROPIC_VERSION = "2023-06-01"
_GOOGLE_MAX_PAGES = 5


class DiscoveryError(Exception):
    """A model list could not be fetched; the message is shown to the admin."""


@dataclass(frozen=True)
class DiscoveredModel:
    id: str
    label: str
    kinds: Kinds


Fetcher = Callable[[httpx.AsyncClient, Optional[str], str], Awaitable[list[DiscoveredModel]]]


async def _get_json(
    client: httpx.AsyncClient,
    url: str,
    headers: Optional[dict[str, str]] = None,
    params: Optional[dict[str, Any]] = None,
) -> Any:
    try:
        response = await client.get(url, headers=headers, params=params)
    except httpx.RequestError as exc:
        raise DiscoveryError("The provider could not be reached.") from exc
    if response.status_code in (401, 403):
        raise DiscoveryError(f"The API key was rejected (HTTP {response.status_code}).")
    if response.is_error:
        raise DiscoveryError(f"The provider returned HTTP {response.status_code}.")
    try:
        return response.json()
    except ValueError as exc:
        raise DiscoveryError("The provider sent an unexpected response.") from exc


def _items(payload: Any, key: str = "data") -> list[dict[str, Any]]:
    """Return the dict entries of `{key: [...]}` or of a bare list payload."""
    items = payload.get(key) if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise DiscoveryError("The provider sent an unexpected response.")
    return [item for item in items if isinstance(item, dict)]


def _model(item_id: Any, label: Any, kinds: Kinds) -> Optional[DiscoveredModel]:
    model_id = str(item_id or "").strip()
    if not model_id or not kinds:
        return None
    return DiscoveredModel(id=model_id, label=str(label or model_id).strip(), kinds=kinds)


def _bearer(api_key: Optional[str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


async def fetch_openai(
    client: httpx.AsyncClient, api_key: Optional[str], base_url: str
) -> list[DiscoveredModel]:
    payload = await _get_json(client, f"{base_url}/models", headers=_bearer(api_key))
    models = (
        _model(i.get("id"), i.get("id"), classify_openai(str(i.get("id") or "")))
        for i in _items(payload)
    )
    return [m for m in models if m]


async def fetch_openai_compatible(
    client: httpx.AsyncClient, api_key: Optional[str], base_url: str
) -> list[DiscoveredModel]:
    """DeepSeek, Kimi and MiniMax only serve chat models from /models."""
    payload = await _get_json(client, f"{base_url}/models", headers=_bearer(api_key))
    models = (_model(i.get("id"), i.get("name") or i.get("id"), LLM) for i in _items(payload))
    return [m for m in models if m]


async def fetch_anthropic(
    client: httpx.AsyncClient, api_key: Optional[str], base_url: str
) -> list[DiscoveredModel]:
    headers = {"x-api-key": api_key or "", "anthropic-version": ANTHROPIC_VERSION}
    payload = await _get_json(client, f"{base_url}/models", headers=headers, params={"limit": 1000})
    models = (_model(i.get("id"), i.get("display_name"), LLM) for i in _items(payload))
    return [m for m in models if m]


def _google_models(payload: Any) -> list[DiscoveredModel]:
    found: list[DiscoveredModel] = []
    for item in _items(payload, key="models"):
        model_id = str(item.get("name") or "").removeprefix("models/")
        methods = item.get("supportedGenerationMethods") or []
        model = _model(model_id, item.get("displayName"), classify_google(model_id, methods))
        if model:
            found.append(model)
    return found


async def fetch_google(
    client: httpx.AsyncClient, api_key: Optional[str], base_url: str
) -> list[DiscoveredModel]:
    headers = {"x-goog-api-key": api_key or ""}
    found: list[DiscoveredModel] = []
    page_token = ""
    for _ in range(_GOOGLE_MAX_PAGES):
        params = {"pageSize": 1000, **({"pageToken": page_token} if page_token else {})}
        payload = await _get_json(client, f"{base_url}/models", headers=headers, params=params)
        found.extend(_google_models(payload))
        page_token = payload.get("nextPageToken") if isinstance(payload, dict) else ""
        if not page_token:
            break
    return found


async def fetch_openrouter(
    client: httpx.AsyncClient, api_key: Optional[str], base_url: str
) -> list[DiscoveredModel]:
    payload = await _get_json(client, f"{base_url}/models", headers=_bearer(api_key))
    models = (_model(i.get("id"), i.get("name"), classify_openrouter(i)) for i in _items(payload))
    return [m for m in models if m]


async def fetch_ollama(
    client: httpx.AsyncClient, _api_key: Optional[str], base_url: str
) -> list[DiscoveredModel]:
    """Ollama does not tag image models, so every installed model is offered for both roles."""
    payload = await _get_json(client, f"{base_url}/api/tags")
    models = (
        _model(i.get("name"), i.get("name"), LLM_AND_IMAGE) for i in _items(payload, key="models")
    )
    return [m for m in models if m]


async def fetch_stable_diffusion(
    client: httpx.AsyncClient, _api_key: Optional[str], base_url: str
) -> list[DiscoveredModel]:
    payload = await _get_json(client, f"{base_url}/sdapi/v1/sd-models")
    checkpoints = (
        _model(i.get("title") or i.get("model_name"), i.get("model_name"), IMAGE)
        for i in _items(payload, key="data")
    )
    default = DiscoveredModel(id="default", label="Currently loaded checkpoint", kinds=IMAGE)
    return [default, *(m for m in checkpoints if m)]


async def fetch_comfyui(
    client: httpx.AsyncClient, _api_key: Optional[str], base_url: str
) -> list[DiscoveredModel]:
    payload = await _get_json(client, f"{base_url}/object_info/CheckpointLoaderSimple")
    try:
        checkpoints = payload["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]
    except (KeyError, TypeError, IndexError) as exc:
        raise DiscoveryError("ComfyUI did not expose checkpoint loader options.") from exc
    if not isinstance(checkpoints, list):
        raise DiscoveryError("ComfyUI returned an invalid checkpoint list.")
    return [
        DiscoveredModel(id=name, label=name, kinds=IMAGE)
        for name in checkpoints
        if isinstance(name, str)
    ]
