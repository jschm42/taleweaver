"""Lumigen MCP image transport: JSON-RPC tool calls for model discovery and image generation."""

from __future__ import annotations

import json
import math
import ssl
from typing import Any, Optional
from urllib.parse import urlparse

import httpx

from backend.utils.path_security import validate_provider_url

DEFAULT_LUMIGEN_URL = "https://127.0.0.1:7003/mcp"
DEFAULT_LUMIGEN_TIMEOUT = 300
_LOOPBACK_HOSTS = frozenset(("127.0.0.1", "localhost", "::1"))


def ssl_verify_for_url(url: str) -> bool | ssl.SSLContext:
    """Allow self-signed TLS certificates on local loopback Lumigen Docker endpoints."""
    parsed = urlparse(url)
    if parsed.scheme == "https" and (parsed.hostname or "").lower() in _LOOPBACK_HOSTS:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    return True


def _headers(api_key: Optional[str]) -> dict[str, str]:
    headers = {"Accept": "application/json, text/event-stream"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _extract_json_rpc(response: httpx.Response) -> dict[str, Any]:
    if response.status_code == 401:
        raise ValueError("Lumigen MCP rejected the Bearer token (HTTP 401).")
    if response.is_error:
        raise ValueError(f"Lumigen MCP rejected request (HTTP {response.status_code}).")
    content_type = response.headers.get("content-type", "")
    if "text/event-stream" in content_type:
        last: dict[str, Any] = {}
        for line in response.text.splitlines():
            if line.startswith("data:"):
                raw = line[5:].strip()
                if raw:
                    last = json.loads(raw)
        return last
    return response.json()


def _tool_error_message(result: dict[str, Any]) -> str:
    structured = result.get("structuredContent") or {}
    if isinstance(structured, dict) and structured.get("error"):
        return str(structured["error"])
    for block in result.get("content") or []:
        if isinstance(block, dict) and block.get("text"):
            return str(block["text"])
    return "Lumigen MCP tool call failed."


async def call_mcp_tool(
    client: httpx.AsyncClient,
    url: str,
    api_key: Optional[str],
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Invoke a Lumigen MCP tool over Streamable HTTP JSON-RPC."""
    validated_url = validate_provider_url(url)
    response = await client.post(
        validated_url,
        headers=_headers(api_key),
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        },
    )
    payload = _extract_json_rpc(response)
    if "error" in payload:
        err = payload["error"]
        msg = err.get("message") if isinstance(err, dict) else str(err)
        raise ValueError(f"Lumigen MCP error: {msg}")
    result = payload.get("result") or {}
    if result.get("isError"):
        raise ValueError(_tool_error_message(result))
    return result


async def _list_items(
    client: httpx.AsyncClient,
    base_url: str,
    api_key: Optional[str],
    tool_name: str,
    key: str,
) -> list[dict[str, Any]]:
    result = await call_mcp_tool(client, base_url, api_key, tool_name, {})
    structured = result.get("structuredContent")
    if isinstance(structured, dict) and isinstance(structured.get(key), list):
        return structured[key]
    for block in result.get("content") or []:
        if isinstance(block, dict) and block.get("text"):
            parsed = json.loads(block["text"])
            if isinstance(parsed, dict) and isinstance(parsed.get(key), list):
                return parsed[key]
    raise ValueError(f"Lumigen MCP did not return '{key}'.")


async def list_models(
    client: httpx.AsyncClient,
    base_url: str,
    api_key: Optional[str],
) -> list[dict[str, Any]]:
    """Return the image models configured on the Lumigen MCP server."""
    return await _list_items(client, base_url, api_key, "list_models", "models")


async def list_profiles(
    client: httpx.AsyncClient,
    base_url: str,
    api_key: Optional[str],
) -> list[dict[str, Any]]:
    """Return the generation profiles configured on the Lumigen MCP server."""
    return await _list_items(client, base_url, api_key, "list_profiles", "profiles")


async def list_categories(
    client: httpx.AsyncClient,
    base_url: str,
    api_key: Optional[str],
) -> list[dict[str, Any]]:
    """Return the gallery categories configured on the Lumigen MCP server."""
    return await _list_items(client, base_url, api_key, "list_categories", "categories")


async def discover_options(
    base_url: str,
    api_key: Optional[str],
    *,
    client: Optional[httpx.AsyncClient] = None,
) -> dict[str, list[dict[str, Any]]]:
    """Fetch profiles and categories from the Lumigen MCP server."""
    url = validate_provider_url(base_url or DEFAULT_LUMIGEN_URL)
    if client is not None:
        return {
            "profiles": await list_profiles(client, url, api_key),
            "categories": await list_categories(client, url, api_key),
        }
    async with httpx.AsyncClient(
        timeout=15.0, verify=ssl_verify_for_url(url), follow_redirects=False
    ) as own_client:
        return {
            "profiles": await list_profiles(own_client, url, api_key),
            "categories": await list_categories(own_client, url, api_key),
        }


def _aspect_ratio(provider_options: dict[str, Any]) -> Optional[str]:
    ratio = provider_options.get("aspect_ratio")
    if isinstance(ratio, str) and ratio.strip():
        return ratio.strip()
    width, height = provider_options.get("width"), provider_options.get("height")
    if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0:
        divisor = math.gcd(width, height)
        return f"{width // divisor}:{height // divisor}"
    return None


def _extract_image_b64(result: dict[str, Any]) -> str:
    for block in result.get("content") or []:
        if isinstance(block, dict) and block.get("type") == "image" and block.get("data"):
            return str(block["data"])
    structured = result.get("structuredContent") or {}
    status = structured.get("status") if isinstance(structured, dict) else None
    if status and status != "succeeded":
        raise ValueError(f"Lumigen MCP generation ended with status '{status}'.")
    raise ValueError("Lumigen MCP completed without returning image data.")


async def generate_image(
    prompt: str,
    model: str,
    api_key: str | None,
    target_dir: str,
    filename: str | None,
    provider_options: dict[str, Any],
) -> str | None:
    """Generate an image via Lumigen MCP ``generate_image`` and save it locally."""
    from backend.engine.media.media_engine import MediaEngine

    url = validate_provider_url(provider_options.get("lumigen_url") or DEFAULT_LUMIGEN_URL)
    timeout = max(
        5, min(3600, int(provider_options.get("lumigen_timeout") or DEFAULT_LUMIGEN_TIMEOUT))
    )
    arguments: dict[str, Any] = {
        "prompt": prompt,
        "model": model,
        "n_images": 1,
        "wait": True,
        "timeout_seconds": timeout,
        "include_images": "full",
    }
    aspect_ratio = _aspect_ratio(provider_options)
    if aspect_ratio:
        arguments["aspect_ratio"] = aspect_ratio
    profile = str(provider_options.get("lumigen_profile") or "").strip()
    if profile:
        arguments["profile"] = profile
    raw_categories = provider_options.get("lumigen_categories")
    if isinstance(raw_categories, str):
        categories = [c.strip() for c in raw_categories.split(",") if c.strip()]
    elif isinstance(raw_categories, list):
        categories = [str(c).strip() for c in raw_categories if str(c).strip()]
    else:
        categories = []
    if categories:
        arguments["categories"] = categories
    session_title = str(
        provider_options.get("session_title") or provider_options.get("adventure_title") or ""
    ).strip()
    if session_title:
        arguments["session_title"] = session_title
    if provider_options.get("negative_prompt"):
        arguments["negative_prompt"] = str(provider_options["negative_prompt"])
    if provider_options.get("seed") is not None:
        arguments["seed"] = int(provider_options["seed"])

    async with httpx.AsyncClient(
        timeout=timeout + 15, verify=ssl_verify_for_url(url), follow_redirects=False
    ) as client:
        result = await call_mcp_tool(client, url, api_key, "generate_image", arguments)

    b64_data = _extract_image_b64(result)
    return await MediaEngine._save_b64_image(
        b64_data,
        target_dir,
        filename,
        image_format=provider_options.get("image_format") or "jpeg",
        quality=provider_options.get("image_quality") or 85,
    )
