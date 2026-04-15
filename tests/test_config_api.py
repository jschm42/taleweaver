"""
Tests for the Settings / Config REST API (Package 4).

Covers: saving encrypted API keys for different providers.
"""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_save_api_key_creates_user(client: AsyncClient):
    """
    Saving an API key for the first time creates the default user
    and returns a success status.
    """
    # Arrange
    payload = {"provider": "openai", "api_key": "sk-test-key-123"}

    # Act
    resp = await client.post("/api/settings/keys", json=payload)

    # Assert
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert "openai" in data["message"]


async def test_save_api_key_multiple_providers(client: AsyncClient):
    """Saving keys for two providers both succeed independently."""
    for provider, key in [("openai", "sk-openai"), ("anthropic", "sk-anthropic")]:
        resp = await client.post(
            "/api/settings/keys",
            json={"provider": provider, "api_key": key},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"


async def test_save_api_key_overwrites_existing(client: AsyncClient):
    """Saving a key for the same provider twice overwrites the first key."""
    payload = {"provider": "openai", "api_key": "sk-first"}
    await client.post("/api/settings/keys", json=payload)

    payload["api_key"] = "sk-second"
    resp = await client.post("/api/settings/keys", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"


async def test_save_t2i_settings_with_ollama_fields(client: AsyncClient):
    """Saving Ollama image settings persists optional local generation controls."""
    payload = {
        "simple_model": "x/flux2-klein",
        "advanced_model": "x/flux2-klein",
        "provider": "ollama",
        "ollama_url": "http://localhost:11434",
        "width": 1024,
        "height": 768,
        "steps": 30,
        "seed": 42,
        "negative_prompt": "blurry, artifacts",
    }

    save_resp = await client.post("/api/settings/t2i", json=payload)
    assert save_resp.status_code == 200
    assert save_resp.json()["status"] == "success"

    settings_resp = await client.get("/api/settings")
    assert settings_resp.status_code == 200
    data = settings_resp.json()
    assert data["t2i_settings"] == payload


async def test_get_settings_returns_extended_t2i_defaults(client: AsyncClient):
    """Default settings include Ollama-compatible fields for forward compatibility."""
    resp = await client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert "t2i_settings" in data

    t2i = data["t2i_settings"]
    assert t2i["simple_model"] == "openai/dall-e-2"
    assert t2i["advanced_model"] == "openai/dall-e-3"
    assert t2i["provider"] == "openai"
    assert t2i["ollama_url"] == "http://localhost:11434"
    assert t2i["width"] is None
    assert t2i["height"] is None
    assert t2i["steps"] is None
    assert t2i["seed"] is None
    assert t2i["negative_prompt"] is None


async def test_save_llm_settings_with_ollama_url(client: AsyncClient):
    """Saving LLM settings should persist local Ollama endpoint configuration."""
    payload = {
        "small_model": "llama3.2",
        "complex_model": "qwen2.5",
        "preferred_provider": "ollama",
        "ollama_url": "http://localhost:11434",
    }

    save_resp = await client.post("/api/settings/llm", json=payload)
    assert save_resp.status_code == 200
    assert save_resp.json()["status"] == "success"

    settings_resp = await client.get("/api/settings")
    assert settings_resp.status_code == 200
    assert settings_resp.json()["llm_settings"] == payload


async def test_save_llm_settings_normalizes_openrouter_models(client: AsyncClient):
    """OpenRouter LLM settings should not store stale provider prefixes."""
    payload = {
        "small_model": "openai/gpt-oss-120b",
        "complex_model": "openai/gpt-5.4",
        "preferred_provider": "openrouter",
        "ollama_url": "http://localhost:11434",
    }

    save_resp = await client.post("/api/settings/llm", json=payload)
    assert save_resp.status_code == 200
    assert save_resp.json()["status"] == "success"

    settings_resp = await client.get("/api/settings")
    assert settings_resp.status_code == 200
    data = settings_resp.json()["llm_settings"]
    assert data["small_model"] == "gpt-oss-120b"
    assert data["complex_model"] == "gpt-5.4"
    assert data["preferred_provider"] == "openrouter"
    assert data["ollama_url"] == "http://localhost:11434"


async def test_get_settings_returns_llm_ollama_default(client: AsyncClient):
    """Default llm settings include ollama_url for local provider use."""
    resp = await client.get("/api/settings")
    assert resp.status_code == 200
    llm = resp.json()["llm_settings"]
    assert llm["small_model"] == "openai/gpt-4o-mini"
    assert llm["complex_model"] == "openai/gpt-4o-mini"
    assert llm["preferred_provider"] == "openai"
    assert llm["ollama_url"] == "http://localhost:11434"
