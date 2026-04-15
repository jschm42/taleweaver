"""Tests for MediaEngine provider routing and Ollama fallback behavior."""
import pytest

from backend.engine.media_engine import MediaEngine

pytestmark = pytest.mark.asyncio


class _FakeLiteLLMResponse:
    def __init__(self, data):
        self.data = data


async def test_generate_image_ollama_uses_litellm_payload(monkeypatch):
    """Ollama provider accepts keyless generation and saves b64 from LiteLLM payload."""
    captured_kwargs = {}

    def fake_image_generation(**kwargs):
        captured_kwargs.update(kwargs)
        return _FakeLiteLLMResponse([{"b64_json": "ZmFrZQ=="}])

    async def fake_save_b64(_b64, _target_dir, _filename):
        return "/data/adventures/test/generated.png"

    monkeypatch.setattr("backend.engine.media_engine.litellm.image_generation", fake_image_generation)
    monkeypatch.setattr(MediaEngine, "_save_b64_image", fake_save_b64)

    result = await MediaEngine.generate_image(
        prompt="A torch-lit dungeon corridor",
        model="x/flux2-klein",
        api_key=None,
        provider="ollama",
        target_dir="/tmp",
        filename="img.png",
        provider_options={"ollama_url": "http://localhost:11434"},
    )

    assert result == "/data/adventures/test/generated.png"
    assert captured_kwargs["api_base"] == "http://localhost:11434"
    assert captured_kwargs["custom_llm_provider"] == "ollama"


async def test_generate_image_ollama_falls_back_to_direct_http(monkeypatch):
    """When LiteLLM fails for Ollama, MediaEngine should use direct HTTP fallback."""
    calls = {"fallback": 0}

    def fake_image_generation(**_kwargs):
        raise RuntimeError("provider not supported")

    async def fake_direct(**kwargs):
        calls["fallback"] += 1
        assert kwargs["ollama_url"] == "http://localhost:11434"
        assert kwargs["model"] == "x/flux2-klein"
        return "/data/adventures/test/fallback.png"

    monkeypatch.setattr("backend.engine.media_engine.litellm.image_generation", fake_image_generation)
    monkeypatch.setattr(MediaEngine, "_generate_image_ollama_direct", fake_direct)

    result = await MediaEngine.generate_image(
        prompt="A moonlit forest",
        model="x/flux2-klein",
        api_key=None,
        provider="ollama",
        target_dir="/tmp",
        provider_options={"ollama_url": "http://localhost:11434"},
    )

    assert result == "/data/adventures/test/fallback.png"
    assert calls["fallback"] == 1


async def test_generate_image_requires_key_for_cloud_provider():
    """Non-local providers still require an API key."""
    with pytest.raises(ValueError, match="Missing API key"):
        await MediaEngine.generate_image(
            prompt="A tavern",
            model="openai/dall-e-3",
            api_key=None,
            provider="openai",
            target_dir="/tmp",
        )


async def test_generate_image_ollama_raises_if_local_generation_fails(monkeypatch):
    """When Ollama is configured, image generation failures must abort instead of returning None."""

    def fake_image_generation(**_kwargs):
        raise RuntimeError("ollama adapter error")

    async def fake_direct(**_kwargs):
        return None

    monkeypatch.setattr("backend.engine.media_engine.litellm.image_generation", fake_image_generation)
    monkeypatch.setattr(MediaEngine, "_generate_image_ollama_direct", fake_direct)

    with pytest.raises(RuntimeError, match="Ollama image generation failed"):
        await MediaEngine.generate_image(
            prompt="A castle in fog",
            model="x/flux2-klein",
            api_key=None,
            provider="ollama",
            target_dir="/tmp",
            provider_options={"ollama_url": "http://localhost:11434"},
        )


async def test_generate_image_ollama_rejects_cloud_model_prefix():
    """Ollama provider must not accept cloud-prefixed image models."""
    with pytest.raises(ValueError, match="Provider is 'ollama' but image model"):
        await MediaEngine.generate_image(
            prompt="A snowy mountain",
            model="openai/dall-e-3",
            api_key=None,
            provider="ollama",
            target_dir="/tmp",
            provider_options={"ollama_url": "http://localhost:11434"},
        )
