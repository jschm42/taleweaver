"""Model discovery: provider adapters, capability filtering, cache and fallback.

All HTTP traffic goes through ``httpx.MockTransport``; no test touches the network.
"""

import httpx
import pytest

from backend.core.config import settings
from backend.services import model_discovery
from backend.services.model_discovery.classify import classify_google, classify_openai

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _empty_cache():
    model_discovery.clear_cache()
    yield
    model_discovery.clear_cache()


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _ids(result) -> list[str]:
    return [m.id for m in result.models]


@pytest.mark.parametrize(
    ("model_id", "expected"),
    [
        ("gpt-5.4", {"llm"}),
        ("o3-mini", {"llm"}),
        ("gpt-image-1.5", {"image"}),
        ("dall-e-3", {"image"}),
        ("gpt-4o-realtime-preview", set()),
        ("gpt-4o-mini-tts", set()),
        ("text-embedding-3-large", set()),
        ("whisper-1", set()),
    ],
)
async def test_classify_openai(model_id, expected):
    assert classify_openai(model_id) == expected


@pytest.mark.parametrize(
    ("model_id", "methods", "expected"),
    [
        ("gemini-2.5-flash", ["generateContent"], {"llm"}),
        ("gemini-2.5-flash-image", ["generateContent"], {"image"}),
        ("imagen-4.0-generate-001", ["predict"], {"image"}),
        ("gemini-2.5-flash-preview-tts", ["generateContent"], set()),
        ("gemini-embedding-001", ["embedContent"], set()),
        ("veo-3.0-generate-001", ["predictLongRunning"], set()),
    ],
)
async def test_classify_google(model_id, methods, expected):
    assert classify_google(model_id, methods) == expected


async def test_openai_uses_bearer_and_filters_by_kind():
    # Arrange
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization", "")
        data = [{"id": "gpt-5.4"}, {"id": "gpt-image-1.5"}, {"id": "whisper-1"}]
        return httpx.Response(200, json={"data": data})

    # Act
    async with _client(handler) as client:
        llm = await model_discovery.discover_models("openai", "llm", "sk-test", client=client)
        image = await model_discovery.discover_models("openai", "image", "sk-test", client=client)

    # Assert
    assert seen["auth"] == "Bearer sk-test"
    assert (llm.source, _ids(llm)) == ("live", ["gpt-5.4"])
    assert _ids(image) == ["gpt-image-1.5"]


async def test_anthropic_uses_x_api_key_header():
    # Arrange
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.headers)
        data = [{"id": "claude-sonnet-4-6", "display_name": "Claude Sonnet 4.6"}]
        return httpx.Response(200, json={"data": data})

    # Act
    async with _client(handler) as client:
        result = await model_discovery.discover_models("anthropic", "llm", "ak", client=client)

    # Assert
    assert seen["x-api-key"] == "ak"
    assert "anthropic-version" in seen
    assert "authorization" not in seen
    assert [(m.id, m.label) for m in result.models] == [("claude-sonnet-4-6", "Claude Sonnet 4.6")]


async def test_google_paginates_and_strips_prefix():
    # Arrange
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-goog-api-key"] == "gk"
        if request.url.params.get("pageToken") == "p2":
            models = [
                {
                    "name": "models/imagen-4.0-generate-001",
                    "supportedGenerationMethods": ["predict"],
                }
            ]
            return httpx.Response(200, json={"models": models})
        models = [
            {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]}
        ]
        return httpx.Response(200, json={"models": models, "nextPageToken": "p2"})

    # Act
    async with _client(handler) as client:
        llm = await model_discovery.discover_models("google", "llm", "gk", client=client)
        image = await model_discovery.discover_models("google", "image", "gk", client=client)

    # Assert
    assert _ids(llm) == ["gemini-2.5-flash"]
    assert _ids(image) == ["imagen-4.0-generate-001"]


async def test_openrouter_splits_by_output_modality_without_key():
    # Arrange
    def handler(request: httpx.Request) -> httpx.Response:
        data = [
            {"id": "openai/gpt-5-mini", "architecture": {"output_modalities": ["text"]}},
            {
                "id": "google/gemini-3.1-flash-image-preview",
                "architecture": {"output_modalities": ["image", "text"]},
            },
        ]
        return httpx.Response(200, json={"data": data})

    # Act
    async with _client(handler) as client:
        llm = await model_discovery.discover_models("openrouter", "llm", None, client=client)
        image = await model_discovery.discover_models("openrouter", "image", None, client=client)

    # Assert
    assert _ids(llm) == ["openai/gpt-5-mini"]
    assert _ids(image) == ["google/gemini-3.1-flash-image-preview"]


async def test_openrouter_asks_for_all_output_modalities():
    """Without the filter OpenRouter leaves out image-only models such as gpt-image."""

    # Arrange
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("output_modalities") != "all":
            return httpx.Response(200, json={"data": []})
        data = [{"id": "openai/gpt-image-2", "architecture": {"output_modalities": ["image"]}}]
        return httpx.Response(200, json={"data": data})

    # Act
    async with _client(handler) as client:
        image = await model_discovery.discover_models("openrouter", "image", None, client=client)

    # Assert
    assert _ids(image) == ["openai/gpt-image-2"]


async def test_ollama_uses_custom_base_url():
    # Arrange
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json={"models": [{"name": "qwen2.5:7b"}]})

    # Act
    async with _client(handler) as client:
        result = await model_discovery.discover_models(
            "ollama", "llm", None, base_url="http://gpu-box:11434/", client=client
        )

    # Assert
    assert seen == ["http://gpu-box:11434/api/tags"]
    assert _ids(result) == ["qwen2.5:7b"]


async def test_key_bearing_provider_ignores_custom_base_url():
    # Arrange
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.host)
        return httpx.Response(200, json={"data": []})

    # Act
    async with _client(handler) as client:
        await model_discovery.discover_models(
            "openai", "llm", "sk-test", base_url="https://evil.example", client=client
        )

    # Assert
    assert seen == ["api.openai.com"]


async def test_rejected_key_falls_back_to_builtin_list():
    # Arrange
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "bad key"})

    # Act
    async with _client(handler) as client:
        result = await model_discovery.discover_models("openai", "llm", "sk-bad", client=client)

    # Assert
    assert result.source == "fallback"
    assert "rejected" in result.error
    assert "gpt-5.4" in _ids(result)


async def test_missing_key_skips_request():
    # Arrange
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request expected")

    # Act
    async with _client(handler) as client:
        result = await model_discovery.discover_models("anthropic", "llm", None, client=client)

    # Assert
    assert (result.source, result.error) == ("fallback", "No API key configured.")


async def test_unreachable_provider_reports_error():
    # Arrange
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    # Act
    async with _client(handler) as client:
        result = await model_discovery.discover_models("ollama", "llm", None, client=client)

    # Assert
    assert result.source == "fallback"
    assert result.error == "The provider could not be reached."


async def test_results_are_cached_until_refresh():
    # Arrange
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(200, json={"data": [{"id": "deepseek-v4-pro"}]})

    # Act
    async with _client(handler) as client:
        await model_discovery.discover_models("deepseek", "llm", "dk", client=client)
        await model_discovery.discover_models("deepseek", "llm", "dk", client=client)
        await model_discovery.discover_models("deepseek", "llm", "dk", refresh=True, client=client)

    # Assert
    assert len(calls) == 2


async def test_black_forest_labs_uses_static_list():
    # Act
    result = await model_discovery.discover_models("black_forest_labs", "image", "bk")

    # Assert
    assert result.source == "static"
    assert "flux-2-pro" in _ids(result)


async def test_endpoint_rejects_unsupported_kind(auth_client):
    # Act
    response = await auth_client.get(
        "/api/settings/models", params={"provider": "anthropic", "kind": "image"}
    )

    # Assert
    assert response.status_code == 400


async def test_endpoint_returns_fallback_without_key(auth_client, monkeypatch):
    # Arrange
    monkeypatch.setattr(type(settings), "get_env_api_key", lambda _self, _provider: None)

    # Act
    response = await auth_client.get(
        "/api/settings/models", params={"provider": "deepseek", "kind": "llm"}
    )

    # Assert
    body = response.json()
    assert response.status_code == 200
    assert body["source"] == "fallback"
    assert body["error"] == "No API key configured."
    assert {"id": "deepseek-v4-pro", "label": "deepseek-v4-pro"} in body["models"]
