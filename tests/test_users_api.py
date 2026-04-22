import pytest
from httpx import AsyncClient

from backend.core.auth import create_access_token, get_password_hash
from backend.models.user import User
from tests.conftest import TestSessionLocal


pytestmark = pytest.mark.asyncio


async def _create_user(*, username: str, role: str = "admin", bio: str | None = None) -> None:
    async with TestSessionLocal() as session:
        session.add(
            User(
                username=username,
                hashed_password=get_password_hash("pw"),
                role=role,
                bio=bio,
                t2i_settings={
                    "simple_model": "test-simple-vision",
                    "simple_model_provider": "ollama",
                },
            )
        )
        await session.commit()


async def test_generate_profile_image_uses_bio_prompt(monkeypatch: pytest.MonkeyPatch, client: AsyncClient) -> None:
    await _create_user(username="bio_user", bio="A battle mage with ember eyes")

    captured: dict[str, str | None] = {}

    async def fake_generate_image(*, prompt, model, api_key, provider, target_dir, filename, provider_options):
        captured["prompt"] = prompt
        captured["model"] = model
        captured["provider"] = provider
        return "/data/users/generated_bio.png"

    monkeypatch.setattr("backend.engine.media_engine.MediaEngine.generate_image", fake_generate_image)

    headers = {"Authorization": f"Bearer {create_access_token({'sub': 'bio_user'})}"}
    response = await client.post("/api/users/me/profile-image/generate", headers=headers)

    assert response.status_code == 200
    assert captured["prompt"] == "A battle mage with ember eyes"
    assert captured["model"] == "test-simple-vision"
    assert captured["provider"] == "ollama"
    assert response.json()["profile_image_url"] == "/data/users/generated_bio.png"


async def test_generate_profile_image_falls_back_to_default_prompt(monkeypatch: pytest.MonkeyPatch, client: AsyncClient) -> None:
    await _create_user(username="no_bio_user", bio=None)

    captured: dict[str, str | None] = {}

    async def fake_generate_image(*, prompt, model, api_key, provider, target_dir, filename, provider_options):
        captured["prompt"] = prompt
        captured["model"] = model
        captured["provider"] = provider
        return "/data/users/generated_default.png"

    monkeypatch.setattr("backend.engine.media_engine.MediaEngine.generate_image", fake_generate_image)

    headers = {"Authorization": f"Bearer {create_access_token({'sub': 'no_bio_user'})}"}
    response = await client.post("/api/users/me/profile-image/generate", headers=headers)

    assert response.status_code == 200
    assert captured["prompt"] == "A fantasy roleplaying avatar"
    assert captured["model"] == "test-simple-vision"
    assert captured["provider"] == "ollama"
    assert response.json()["profile_image_url"] == "/data/users/generated_default.png"


async def test_generate_profile_image_prefers_request_bio_prompt(monkeypatch: pytest.MonkeyPatch, client: AsyncClient) -> None:
    await _create_user(username="override_bio_user", bio=None)

    captured: dict[str, str | None] = {}

    async def fake_generate_image(*, prompt, model, api_key, provider, target_dir, filename, provider_options):
        captured["prompt"] = prompt
        captured["model"] = model
        captured["provider"] = provider
        return "/data/users/generated_override.png"

    monkeypatch.setattr("backend.engine.media_engine.MediaEngine.generate_image", fake_generate_image)

    headers = {"Authorization": f"Bearer {create_access_token({'sub': 'override_bio_user'})}"}
    response = await client.post(
        "/api/users/me/profile-image/generate",
        headers=headers,
        json={"bio": "A masked ranger with a silver compass"},
    )

    assert response.status_code == 200
    assert captured["prompt"] == "A masked ranger with a silver compass"
    assert captured["model"] == "test-simple-vision"
    assert captured["provider"] == "ollama"
    assert response.json()["profile_image_url"] == "/data/users/generated_override.png"
