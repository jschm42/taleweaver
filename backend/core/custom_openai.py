"""Configuration and discovery for administrator-managed OpenAI-compatible servers."""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import time
from typing import Any
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException
from pydantic import BaseModel

from backend.core.api_keys import is_blocked
from backend.utils.path_security import _resolve_host_ips, validate_provider_url

logger = logging.getLogger(__name__)


def validate_custom_url(url: str) -> str:
    """Reuse provider policy while always excluding metadata and ambiguous URL forms."""
    try:
        from backend.core.config import settings

        allow_private = (
            settings.ALLOW_PRIVATE_NETWORK_MODELS
            and "ALLOW_PRIVATE_NETWORK_MODELS" in settings.model_fields_set
        )
        normalized = validate_provider_url(url, allow_private=allow_private).rstrip("/")
        parsed = urlsplit(normalized)
        if parsed.port is not None and not 1 <= parsed.port <= 65535:
            raise ValueError("Endpoint port must be between 1 and 65535.")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Base URL must not contain credentials, a query, or a fragment.")
        if not parsed.path.endswith("/v1"):
            raise ValueError("Base URL must end in /v1 (for example http://127.0.0.1:8080/v1).")
        addresses = _resolve_host_ips(parsed.hostname)
        if not addresses:
            raise ValueError("Could not resolve endpoint hostname.")
        for address in addresses:
            ip = ipaddress.ip_address(address)
            forbidden = (
                ip.is_link_local
                or ip.is_unspecified
                or ip.is_multicast
                or (ip.is_reserved and not ip.is_loopback)
                or str(ip) in {"100.100.100.200", "fd00:ec2::254"}
            )
            if forbidden:
                raise ValueError(
                    "Metadata, link-local, reserved and multicast endpoints are forbidden."
                )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return normalized


def configure_custom_router(router: Any, llm_settings: dict, prefix: str = "") -> None:
    """Require an explicit validated base and use the existing encrypted provider vault."""
    per_pass_url = (llm_settings.get(f"{prefix}custom_openai_url") or "").strip() if prefix else ""
    base_url = per_pass_url or (llm_settings.get("custom_openai_url") or "").strip()
    router.api_base = validate_custom_url(base_url)
    router.api_key = None
    vault = router.user.encrypted_api_keys or {}
    # A blocked provider (personal key missing / disabled) raises in _get_decrypted_key.
    if vault.get("custom_openai") or is_blocked(vault, "custom_openai"):
        router.api_key = router._get_decrypted_key("custom_openai")
    elif "openrouter.ai" in (router.api_base or "") and vault.get("openrouter"):
        router.api_key = router._get_decrypted_key("openrouter")
    per_pass_timeout = llm_settings.get(f"{prefix}custom_openai_timeout") if prefix else None
    timeout_val = per_pass_timeout or llm_settings.get("custom_openai_timeout") or 300
    router.request_timeout = max(1, min(3600, int(timeout_val)))

    per_pass_format = (
        (llm_settings.get(f"{prefix}custom_openai_response_format") or "").strip() if prefix else ""
    )
    router.custom_response_format = (
        per_pass_format or llm_settings.get("custom_openai_response_format") or "prompt"
    )
    router.stream_initial_timeout = router.request_timeout
    router.stream_chunk_timeout = router.request_timeout


def _is_transient_custom_error(exc: Exception) -> bool:
    """Detect rate limits, upstream quotas, timeouts, or socket drops for custom endpoints."""
    if getattr(exc, "status_code", None) in {429, 502, 503, 504}:
        return True
    err_type = type(exc).__name__.lower()
    if any(
        term in err_type
        for term in (
            "ratelimit",
            "timeout",
            "connecterror",
            "connecttimeout",
            "readtimeout",
            "apiconnectionerror",
        )
    ):
        return True
    err_msg = str(exc or "").lower()
    return any(
        term in err_msg
        for term in (
            "rate limit",
            "ratelimit",
            "temporarily rate-limited",
            "too many requests",
            "quota",
            "upstream_provider_shared_pool",
            "connection refused",
            "connection reset",
            "remote disconnected",
            "broken pipe",
        )
    )


async def discover_models(base: str, api_key: str | None) -> list[str]:
    """Fetch /models without redirects or a required credential; failures remain actionable."""
    base = validate_custom_url(base)
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
            response = await client.get(f"{base}/models", headers=headers)
        response.raise_for_status()
        payload = response.json()
        models = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(models, list):
            raise ValueError("Expected an OpenAI model list.")
        return sorted(
            {
                item["id"]
                for item in models
                if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"].strip()
            }
        )
    except httpx.TimeoutException as exc:
        raise HTTPException(
            504, "Model detection timed out. Check the server; a manual Model ID can still be used."
        ) from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        message = {
            401: "Authentication failed. Save the endpoint API key in the provider vault.",
            403: "Access denied. Check the endpoint API key and tunnel access policy.",
            404: "This server has no /models endpoint. Enter a Model ID manually.",
        }.get(status, "Model detection failed. Check the Base URL; redirects are not followed.")
        raise HTTPException(502, message) from exc
    except (httpx.RequestError, ValueError, TypeError) as exc:
        raise HTTPException(
            502,
            "Could not detect models. Check the server and Base URL, or enter a Model ID manually.",
        ) from exc


def complete(router: Any, kwargs: dict) -> Any:
    """Use a bounded SDK client so redirects cannot bypass endpoint policy."""
    from openai import OpenAI

    max_retries = 3
    for attempt in range(max_retries):
        try:
            with (
                httpx.Client(follow_redirects=False) as transport,
                OpenAI(
                    api_key=router.api_key or "local-no-key",
                    base_url=validate_custom_url(router.api_base),
                    http_client=transport,
                    max_retries=0,
                ) as client,
            ):
                return router._get_litellm().completion(
                    **kwargs, client=client, request_timeout=router.request_timeout
                )
        except Exception as exc:
            if attempt < max_retries - 1 and _is_transient_custom_error(exc):
                backoff = 1.0 * (attempt + 1)
                logger.warning(
                    "Custom OpenAI call attempt %d/%d failed with %s: %s. Retrying in %.1fs...",
                    attempt + 1,
                    max_retries,
                    type(exc).__name__,
                    exc,
                    backoff,
                )
                time.sleep(backoff)
                continue
            raise


async def acomplete(router: Any, kwargs: dict) -> Any:
    """Keep streaming clients alive until the iterator is consumed, then close them."""
    if kwargs.get("stream"):
        return _stream(router, kwargs)
    from openai import AsyncOpenAI

    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with (
                httpx.AsyncClient(follow_redirects=False) as transport,
                AsyncOpenAI(
                    api_key=router.api_key or "local-no-key",
                    base_url=validate_custom_url(router.api_base),
                    http_client=transport,
                    max_retries=0,
                ) as client,
            ):
                return await router._get_litellm().acompletion(
                    **kwargs, client=client, request_timeout=router.request_timeout
                )
        except Exception as exc:
            if attempt < max_retries - 1 and _is_transient_custom_error(exc):
                backoff = 1.0 * (attempt + 1)
                logger.warning(
                    "Custom OpenAI call attempt %d/%d failed with %s: %s. Retrying in %.1fs...",
                    attempt + 1,
                    max_retries,
                    type(exc).__name__,
                    exc,
                    backoff,
                )
                await asyncio.sleep(backoff)
                continue
            raise


async def _stream(router: Any, kwargs: dict) -> Any:
    from openai import AsyncOpenAI

    max_retries = 3
    for attempt in range(max_retries):
        has_yielded = False
        try:
            async with (
                httpx.AsyncClient(follow_redirects=False) as transport,
                AsyncOpenAI(
                    api_key=router.api_key or "local-no-key",
                    base_url=validate_custom_url(router.api_base),
                    http_client=transport,
                    max_retries=0,
                ) as client,
            ):
                stream = await router._get_litellm().acompletion(
                    **kwargs, client=client, request_timeout=router.request_timeout
                )
                try:
                    async for chunk in stream:
                        has_yielded = True
                        yield chunk
                finally:
                    await stream.aclose()
                return
        except Exception as exc:
            if not has_yielded and attempt < max_retries - 1 and _is_transient_custom_error(exc):
                backoff = 1.0 * (attempt + 1)
                logger.warning(
                    "Custom OpenAI stream attempt %d/%d failed with %s: %s. Retrying in %.1fs...",
                    attempt + 1,
                    max_retries,
                    type(exc).__name__,
                    exc,
                    backoff,
                )
                await asyncio.sleep(backoff)
                continue
            raise


def structured_response_format(router: Any, response_model: type[BaseModel]) -> dict | None:
    """Use only the structured-output capability explicitly selected by the administrator."""
    mode = router.custom_response_format
    if mode == "json_object":
        return {"type": "json_object"}
    if mode == "json_schema":
        return {
            "type": "json_schema",
            "json_schema": {
                "name": response_model.__name__,
                "schema": response_model.model_json_schema(),
            },
        }
    return None


class ConnectionTestResult(BaseModel):
    """Small schema used to check the endpoint's selected structured-output capability."""

    message: str


async def test_connection(router: Any, model: str, structured: bool = True) -> str:
    """Exercise the JSON path for structured passes, or text connectivity for prose passes."""
    if not structured:
        return await router.aexecute_simple_task(
            system_prompt="You are a helpful RPG assistant.",
            user_prompt="Say 'TaleWeaver connection test successful!' in a fantasy style.",
            model=model,
        )
    result = await router.aexecute_complex_task(
        system_prompt="You are a helpful RPG assistant.",
        user_prompt='Return a JSON object with a message saying "TaleWeaver connection test successful!".',
        response_model=ConnectionTestResult,
        model=model,
    )
    return result.message
