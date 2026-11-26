"""Tests for Lumigen MCP model discovery and image generation."""

import base64
import json
import ssl
from io import BytesIO
from unittest.mock import patch

import httpx
import pytest
from PIL import Image

from backend.engine.media import lumigen
from backend.services.model_discovery.service import clear_cache, discover_models


def _png_b64() -> str:
    buf = BytesIO()
    Image.new("RGB", (4, 4), color=(20, 40, 60)).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


@pytest.mark.asyncio
async def test_discover_lumigen_models():
    clear_cache()
    seen_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update(dict(request.headers))
        body = json.loads(request.content.decode("utf-8"))
        assert body["method"] == "tools/call"
        assert body["params"]["name"] == "list_models"
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "isError": False,
                    "structuredContent": {
                        "models": [
                            {"id": 1, "name": "FLUX 3 klein", "provider": "openrouter"},
                            {"id": 2, "name": "FLUX 3", "provider": "bfl"},
                        ]
                    },
                },
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        res = await discover_models(
            "lumigen",
            "image",
            api_key="secret-token",
            base_url="https://127.0.0.1:7003/mcp",
            refresh=True,
            client=client,
        )

    assert res.source == "live"
    assert [m.id for m in res.models] == ["FLUX 3", "FLUX 3 klein"]
    assert res.models[1].label == "FLUX 3 klein (openrouter)"
    assert seen_headers.get("authorization") == "Bearer secret-token"


@pytest.mark.asyncio
async def test_lumigen_generate_image_saves_file(tmp_path, monkeypatch):
    from backend.core.config import settings

    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "isError": False,
                    "content": [{"type": "image", "mimeType": "image/png", "data": _png_b64()}],
                    "structuredContent": {"job_id": 42, "status": "succeeded"},
                },
            },
        )

    real_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with patch("backend.engine.media.lumigen.httpx.AsyncClient", return_value=real_client):
        url = await lumigen.generate_image(
            prompt="a glowing lantern",
            model="FLUX 3 klein",
            api_key="tok-123",
            target_dir=str(tmp_path),
            filename="lantern.webp",
            provider_options={
                "lumigen_url": "https://127.0.0.1:7003/mcp",
                "lumigen_timeout": 120,
                "lumigen_profile": "Music Cover",
                "lumigen_categories": ["Cover", "TaleWeaver"],
                "session_title": "The Crimson Debt",
                "aspect_ratio": "16:9",
                "image_format": "webp",
            },
        )

    assert url is not None
    assert (tmp_path / "lantern.webp").exists()
    assert captured["auth"] == "Bearer tok-123"
    params = captured["body"]["params"]  # type: ignore[index]
    assert params["name"] == "generate_image"
    assert params["arguments"]["model"] == "FLUX 3 klein"
    assert params["arguments"]["profile"] == "Music Cover"
    assert params["arguments"]["categories"] == ["Cover", "TaleWeaver"]
    assert params["arguments"]["session_title"] == "The Crimson Debt"
    assert params["arguments"]["aspect_ratio"] == "16:9"
    assert params["arguments"]["timeout_seconds"] == 120


@pytest.mark.asyncio
async def test_discover_lumigen_options():
    def handler(request: httpx.Request) -> httpx.Response:
        tool = json.loads(request.content.decode("utf-8"))["params"]["name"]
        if tool == "list_profiles":
            sc = {"profiles": [{"id": 1, "name": "Default"}]}
        else:
            sc = {"categories": [{"id": 2, "name": "Cover"}]}
        return httpx.Response(
            200,
            json={"jsonrpc": "2.0", "id": 1, "result": {"isError": False, "structuredContent": sc}},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        res = await lumigen.discover_options("https://127.0.0.1:7003/mcp", "tok", client=client)

    assert res["profiles"] == [{"id": 1, "name": "Default"}]
    assert res["categories"] == [{"id": 2, "name": "Cover"}]


@pytest.mark.parametrize(
    ("url", "expect_self_signed"),
    [
        ("https://127.0.0.1:7003/mcp", True),
        ("https://localhost:7003/mcp", True),
        ("https://[::1]:7003/mcp", True),
        ("https://host.docker.internal:7003/mcp", True),
        ("https://lumigen:7003/mcp", True),
        ("https://192.168.178.57:7003/mcp", True),
        ("https://10.0.0.5:7003/mcp", True),
        ("https://172.18.0.3:7003/mcp", True),
        ("https://lumigen.example.com/mcp", False),
        ("https://8.8.8.8/mcp", False),
        ("http://host.docker.internal:7003/mcp", False),
    ],
)
def test_ssl_verify_for_url(url: str, expect_self_signed: bool):
    result = lumigen.ssl_verify_for_url(url)
    if expect_self_signed:
        assert isinstance(result, ssl.SSLContext)
        assert result.verify_mode == ssl.CERT_NONE
        assert result.check_hostname is False
    else:
        assert result is True
