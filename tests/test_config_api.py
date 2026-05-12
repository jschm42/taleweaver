"""
Tests for the Settings / Config REST API (Package 4).

Covers: saving encrypted API keys for different providers.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient

from backend.core.auth import create_access_token, get_password_hash
from backend.models.user import User
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def client(auth_client: AsyncClient) -> AsyncClient:
    """Settings endpoints require authentication."""
    return auth_client


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
        "simple_model_provider": "ollama",
        "advanced_model": "x/flux2-klein",
        "advanced_model_provider": "ollama",
        "provider": "ollama",
        "ollama_url": "http://localhost:11434",
        "width": 1024,
        "height": 768,
        "steps": 30,
        "seed": 42,
        "image_format": "jpeg",
        "image_quality": 85,
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
    assert t2i["simple_model"] == ""
    assert t2i["advanced_model"] == ""
    assert t2i["provider"] == "openai"
    assert t2i["simple_model_provider"] == "openai"
    assert t2i["advanced_model_provider"] == "openai"
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
        "small_model_provider": "ollama",
        "complex_model": "qwen2.5",
        "complex_model_provider": "ollama",
        "generator_model": "llama3-70b",
        "generator_model_provider": "ollama",
        "preferred_provider": "ollama",
        "ollama_url": "http://localhost:11434",
    }

    save_resp = await client.post("/api/settings/llm", json=payload)
    assert save_resp.status_code == 200
    assert save_resp.json()["status"] == "success"

    settings_resp = await client.get("/api/settings")
    assert settings_resp.status_code == 200
    llm = settings_resp.json()["llm_settings"]
    assert llm["small_model"] == "llama3.2"
    assert llm["small_model_provider"] == "ollama"
    assert llm["complex_model"] == "qwen2.5"
    assert llm["complex_model_provider"] == "ollama"
    assert llm["preferred_provider"] == "ollama"
    assert llm["ollama_url"] == "http://localhost:11434"


async def test_save_llm_settings_normalizes_openrouter_models(client: AsyncClient):
    """OpenRouter LLM settings should not store stale provider prefixes."""
    payload = {
        "small_model": "openai/gpt-oss-120b",
        "small_model_provider": "openrouter",
        "complex_model": "openai/gpt-5.4",
        "complex_model_provider": "openrouter",
        "generator_model": "anthropic/claude-3-opus",
        "generator_model_provider": "openrouter",
        "preferred_provider": "openrouter",
        "ollama_url": "http://localhost:11434",
    }

    save_resp = await client.post("/api/settings/llm", json=payload)
    assert save_resp.status_code == 200
    assert save_resp.json()["status"] == "success"

    settings_resp = await client.get("/api/settings")
    assert settings_resp.status_code == 200
    data = settings_resp.json()["llm_settings"]
    assert data["small_model"] == "openai/gpt-oss-120b"
    assert data["complex_model"] == "openai/gpt-5.4"
    assert data["preferred_provider"] == "openrouter"
    assert data["ollama_url"] == "http://localhost:11434"


async def test_get_settings_returns_llm_ollama_default(client: AsyncClient):
    """Default llm settings include ollama_url for local provider use."""
    resp = await client.get("/api/settings")
    assert resp.status_code == 200
    llm = resp.json()["llm_settings"]
    assert llm["small_model_provider"] == "openai"
    assert llm["complex_model_provider"] == "openai"
    assert llm["small_max_tokens"] == 12288
    assert llm["complex_max_tokens"] == 24576
    assert llm["preferred_provider"] == "openai"
    assert llm["ollama_url"] == "http://localhost:11434"


async def test_get_settings_returns_style_and_tone_catalogs(client: AsyncClient):
    """Default settings should include selectable image styles and tones."""
    resp = await client.get("/api/settings")
    assert resp.status_code == 200
    payload = resp.json()
    assert isinstance(payload["image_styles_catalog"], list)
    assert len(payload["image_styles_catalog"]) > 0
    assert isinstance(payload["tone_catalog"], list)
    assert len(payload["tone_catalog"]) > 0


async def test_save_image_styles_catalog(client: AsyncClient):
    """Admin can persist a custom image style catalog payload."""
    catalog = [
        {
            "id": "chalk-noir",
            "name": "Chalk Noir",
            "description": "Monochrome chalk and smoke.",
            "instruction": "chalk texture, noir composition",
            "image_url": None,
        }
    ]

    save_resp = await client.post("/api/settings/image-styles", json={"items": catalog})
    assert save_resp.status_code == 200
    assert save_resp.json()["status"] == "success"

    settings_resp = await client.get("/api/settings")
    assert settings_resp.status_code == 200
    payload = settings_resp.json()
    assert payload["image_styles_catalog"][0]["id"] == "chalk-noir"


async def test_save_tone_catalog(client: AsyncClient):
    """Admin can persist a custom world tone catalog payload."""
    catalog = [
        {
            "id": "satire",
            "name": "Satire",
            "description": "Playful critique with sharp humor.",
            "instruction": "Keep satirical framing with witty contrast.",
            "image_url": None,
        }
    ]

    save_resp = await client.post("/api/settings/tones", json={"items": catalog})
    assert save_resp.status_code == 200
    assert save_resp.json()["status"] == "success"

    settings_resp = await client.get("/api/settings")
    assert settings_resp.status_code == 200
    payload = settings_resp.json()
    assert payload["tone_catalog"][0]["id"] == "satire"


async def test_settings_are_global_for_all_users(client: AsyncClient):
    """Updating settings as one admin user should apply to all users globally."""
    user_a = "settings_user_a"
    user_b = "settings_user_b"

    async with TestSessionLocal() as session:
        session.add(User(username=user_a, hashed_password=get_password_hash("pw-a"), role="admin"))
        session.add(User(username=user_b, hashed_password=get_password_hash("pw-b"), role="admin"))
        await session.commit()

    headers_a = {"Authorization": f"Bearer {create_access_token({'sub': user_a})}"}
    headers_b = {"Authorization": f"Bearer {create_access_token({'sub': user_b})}"}

    payload_a = {
        "small_model": "llama3.2",
        "small_model_provider": "ollama",
        "small_max_tokens": 1024,
        "small_enable_thinking": False,
        "small_max_thinking_tokens": 256,
        "complex_model": "qwen2.5",
        "complex_model_provider": "ollama",
        "generator_model": "llama3-70b",
        "generator_model_provider": "ollama",
        "complex_max_tokens": 4096,
        "complex_enable_thinking": False,
        "complex_max_thinking_tokens": 512,
        "generator_model": "llama3.2",
        "generator_model_provider": "ollama",
        "preferred_provider": "ollama",
        "ollama_url": "http://localhost:11434",
    }

    save_resp = await client.post("/api/settings/llm", json=payload_a, headers=headers_a)
    assert save_resp.status_code == 200

    a_settings = await client.get("/api/settings", headers=headers_a)
    assert a_settings.status_code == 200
    assert a_settings.json()["llm_settings"]["small_model"] == "llama3.2"

    b_settings = await client.get("/api/settings", headers=headers_b)
    assert b_settings.status_code == 200
    assert b_settings.json()["llm_settings"]["small_model"] == "llama3.2"

