from typing import Optional, Union
import pytest
from httpx import AsyncClient

from backend.core.auth import create_access_token, get_password_hash
from backend.models.user import User
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _create_user(*, username: str, role: str = "admin", bio: Optional[str] = None) -> None:
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

    captured: dict[str, Optional[str]] = {}

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

    captured: dict[str, Optional[str]] = {}

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

    captured: dict[str, Optional[str]] = {}

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


async def test_auth_me_returns_xp_and_counts(client: AsyncClient) -> None:
    from backend.models.avatar import Avatar
    from backend.models.game_session import GameSession

    # 1. Create a user
    username = "xp_user"
    async with TestSessionLocal() as session:
        user = User(
            username=username,
            hashed_password=get_password_hash("pw"),
            role="user"
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

        # 2. Create an avatar with some XP
        avatar = Avatar(
            user_id=user_id,
            name="Hero",
            exp=350
        )
        session.add(avatar)
        await session.commit()
        await session.refresh(avatar)
        avatar_id = avatar.id

        # 3. Create a game session for this user and avatar
        game_session = GameSession(
            user_id=user_id,
            avatar_id=avatar_id,
            adventure_title="Epic Quest",
            status="completed",
        )
        session.add(game_session)
        await session.commit()
        await session.refresh(game_session)
        
        # Populate the game_log on the user manually to simulate finalization
        user.game_log = [{
            "session_id": game_session.id,
            "adventure_title": "Epic Quest",
            "status": "completed",
            "outcome_note": "You won!",
            "completed_at": "2026-05-24T12:00:00Z"
        }]
        await session.commit()

    # 4. Make requests to /api/auth/me
    headers = {"Authorization": f"Bearer {create_access_token({'sub': username})}"}
    response = await client.get("/api/auth/me", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["total_xp"] == 350
    assert data["adventure_count"] == 1
    assert len(data["game_log"]) == 1
    assert data["game_log"][0]["xp"] == 350

