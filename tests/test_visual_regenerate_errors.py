"""Error reporting of POST /api/adventures/{id}/visuals/regenerate."""

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.world_entity import WorldEntity
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio

_PATCH_TARGET = "backend.api.routes.adventures.assets.MediaEngine.generate_adventure_cover"


async def _regenerate_cover(client: AsyncClient, title: str) -> dict:
    create = await client.post("/api/adventures/", json={"title": title, "avatar_name": "Hero"})
    assert create.status_code == 201, create.text
    adventure_id = create.json()["adventure_id"]
    resp = await client.post(
        f"/api/adventures/{adventure_id}/visuals/regenerate",
        json={"target_type": "cover", "target_id": adventure_id, "prompt": "A battlefield."},
    )
    return {"status": resp.status_code, "detail": resp.json().get("detail", "")}


async def test_regenerate_visual_reports_provider_failure_reason(
    auth_client: AsyncClient, monkeypatch
):
    """A failed generation should return the provider's reason instead of a generic message."""

    # Arrange
    async def fake_generate_adventure_cover(**kwargs):
        raise RuntimeError("Prompt rejected by content policy: keyword 'gore'")

    monkeypatch.setattr(_PATCH_TARGET, fake_generate_adventure_cover)

    # Act
    result = await _regenerate_cover(auth_client, "Failing Cover Quest")

    # Assert
    assert result["status"] == 502
    assert "keyword 'gore'" in result["detail"]


async def test_regenerate_visual_reports_missing_image(auth_client: AsyncClient, monkeypatch):
    """A provider returning no image must not be reported as success."""

    # Arrange
    async def fake_generate_adventure_cover(**kwargs):
        return None

    monkeypatch.setattr(_PATCH_TARGET, fake_generate_adventure_cover)

    # Act
    result = await _regenerate_cover(auth_client, "Empty Cover Quest")

    # Assert
    assert result["status"] == 502
    assert "returned no image" in result["detail"]


async def test_regenerate_visual_refuses_recipes(auth_client: AsyncClient, monkeypatch):
    """CONSTRUCTABLE recipes never appear in the world, so they get no image."""

    # Arrange
    create = await auth_client.post(
        "/api/adventures/", json={"title": "Recipe Quest", "avatar_name": "Hero"}
    )
    adventure_id = create.json()["adventure_id"]
    async with TestSessionLocal() as db:
        db.add(WorldEntity(id="RECIPE_LAMP", template_id=adventure_id, entity_type="OBJECT",
                           name="Lamp recipe", description="Combine oil and wick.",
                           current_scene_id="START", item_type="CONSTRUCTABLE", is_hidden=True))  # fmt: skip
        await db.commit()
    generator = AsyncMock(return_value="visuals/recipe.png")
    monkeypatch.setattr(
        "backend.api.routes.adventures.assets.MediaEngine.generate_entity_image", generator
    )

    # Act
    resp = await auth_client.post(
        f"/api/adventures/{adventure_id}/visuals/regenerate",
        json={"target_type": "object", "target_id": "RECIPE_LAMP", "prompt": "A lamp."},
    )

    # Assert
    assert resp.status_code == 400
    assert "Recipes" in resp.json()["detail"]
    generator.assert_not_called()


async def test_regenerate_visual_applies_style_by_default(auth_client: AsyncClient, monkeypatch):
    """By default, configured adventure style instructions should be applied."""
    create = await auth_client.post(
        "/api/adventures/", json={"title": "Style Quest", "avatar_name": "Hero"}
    )
    adventure_id = create.json()["adventure_id"]
    async with TestSessionLocal() as db:
        adv = await db.get(AdventureTemplate, adventure_id)
        assert adv is not None
        adv.selected_image_styles = ["chalk-noir"]
        await db.commit()

    captured = {}

    async def fake_generate_adventure_cover(**kwargs):
        captured.update(kwargs)
        return "/data/adventures/generated/cover.png"

    monkeypatch.setattr(_PATCH_TARGET, fake_generate_adventure_cover)

    resp = await auth_client.post(
        f"/api/adventures/{adventure_id}/visuals/regenerate",
        json={"target_type": "cover", "target_id": adventure_id, "prompt": "A battlefield."},
    )
    assert resp.status_code == 200
    assert captured.get("style_instruction") is not None


async def test_regenerate_visual_omits_style_when_apply_style_false(
    auth_client: AsyncClient, monkeypatch
):
    """When apply_style is False, style instruction should be omitted."""
    create = await auth_client.post(
        "/api/adventures/", json={"title": "No Style Quest", "avatar_name": "Hero"}
    )
    adventure_id = create.json()["adventure_id"]
    async with TestSessionLocal() as db:
        adv = await db.get(AdventureTemplate, adventure_id)
        assert adv is not None
        adv.selected_image_styles = ["chalk-noir"]
        await db.commit()

    captured = {}

    async def fake_generate_adventure_cover(**kwargs):
        captured.update(kwargs)
        return "/data/adventures/generated/cover.png"

    monkeypatch.setattr(_PATCH_TARGET, fake_generate_adventure_cover)

    resp = await auth_client.post(
        f"/api/adventures/{adventure_id}/visuals/regenerate",
        json={
            "target_type": "cover",
            "target_id": adventure_id,
            "prompt": "A battlefield.",
            "apply_style": False,
        },
    )
    assert resp.status_code == 200
    assert captured.get("style_instruction") is None


async def test_enhance_prompt_success(auth_client: AsyncClient, monkeypatch):
    """Enhance prompt should call LLM and return the optimized prompt string."""
    create = await auth_client.post(
        "/api/adventures/", json={"title": "Enhance Quest", "avatar_name": "Hero"}
    )
    adventure_id = create.json()["adventure_id"]

    async def fake_enhance(current_user, prompt, target_type=None, appearance=None, **kwargs):
        return f"Vivid cinematic illustration of {prompt}, dramatic volumetric lighting."

    monkeypatch.setattr(
        "backend.api.routes.adventures.assets.enhance_image_prompt",
        fake_enhance,
    )

    resp = await auth_client.post(
        f"/api/adventures/{adventure_id}/visuals/enhance-prompt",
        json={"prompt": "a lone wizard", "target_type": "npc"},
    )
    assert resp.status_code == 200
    assert resp.json()["enhanced_prompt"] == (
        "Vivid cinematic illustration of a lone wizard, dramatic volumetric lighting."
    )


async def test_enhance_prompt_rejects_empty(auth_client: AsyncClient):
    """Empty prompts must be rejected with 400."""
    create = await auth_client.post(
        "/api/adventures/", json={"title": "Empty Prompt Quest", "avatar_name": "Hero"}
    )
    adventure_id = create.json()["adventure_id"]

    resp = await auth_client.post(
        f"/api/adventures/{adventure_id}/visuals/enhance-prompt",
        json={"prompt": "   "},
    )
    assert resp.status_code == 400
    assert "Prompt cannot be empty" in resp.json()["detail"]


async def test_prompt_enhancer_direct_fallback(monkeypatch):
    """If LLM fails, enhance_image_prompt should gracefully fallback to original prompt."""
    from backend.api.routes.adventures.prompt_enhancer import enhance_image_prompt
    from backend.models.user import User

    fake_user = User(id="user_1", username="tester")

    async def failing_execute(*args, **kwargs):
        raise RuntimeError("LLM exploded")

    monkeypatch.setattr(
        "backend.api.routes.adventures.prompt_enhancer.GameMasterLLM.aexecute_simple_task",
        failing_execute,
    )

    result = await enhance_image_prompt(fake_user, "a lonely knight on a hill")
    assert result == "a lonely knight on a hill"


async def test_regenerate_protagonist_applies_appearance_by_default(
    auth_client: AsyncClient, monkeypatch
):
    """By default, protagonist appearance keywords are included in custom prompt."""
    create = await auth_client.post(
        "/api/adventures/", json={"title": "Protagonist Quest", "avatar_name": "Kael"}
    )
    adventure_id = create.json()["adventure_id"]
    async with TestSessionLocal() as db:
        res = await db.execute(select(Avatar).where(Avatar.template_id == adventure_id).limit(1))
        avatar = res.scalars().first()
        assert avatar is not None
        avatar.appearance = "silver hair, red cape"
        avatar_id = avatar.id
        await db.commit()

    captured = {}

    async def fake_generate_entity_image(prompt, **kwargs):
        captured["prompt"] = prompt
        return "/data/adventures/generated/protagonist.png"

    monkeypatch.setattr(
        "backend.api.routes.adventures.assets.MediaEngine.generate_entity_image",
        fake_generate_entity_image,
    )

    resp = await auth_client.post(
        f"/api/adventures/{adventure_id}/visuals/regenerate",
        json={
            "target_type": "protagonist",
            "target_id": avatar_id,
            "prompt": "A valiant fighter standing before a castle",
        },
    )
    assert resp.status_code == 200
    assert "Visual keywords: silver hair, red cape" in captured["prompt"]


async def test_regenerate_protagonist_omits_appearance_when_disabled(
    auth_client: AsyncClient, monkeypatch
):
    """When apply_appearance is False, appearance keywords are omitted from generation."""
    create = await auth_client.post(
        "/api/adventures/", json={"title": "No App Quest", "avatar_name": "Kael"}
    )
    adventure_id = create.json()["adventure_id"]
    async with TestSessionLocal() as db:
        res = await db.execute(select(Avatar).where(Avatar.template_id == adventure_id).limit(1))
        avatar = res.scalars().first()
        assert avatar is not None
        avatar.appearance = "silver hair, red cape"
        avatar_id = avatar.id
        await db.commit()

    captured = {}

    async def fake_generate_entity_image(prompt, **kwargs):
        captured["prompt"] = prompt
        return "/data/adventures/generated/protagonist.png"

    monkeypatch.setattr(
        "backend.api.routes.adventures.assets.MediaEngine.generate_entity_image",
        fake_generate_entity_image,
    )

    resp = await auth_client.post(
        f"/api/adventures/{adventure_id}/visuals/regenerate",
        json={
            "target_type": "protagonist",
            "target_id": avatar_id,
            "prompt": "A valiant fighter standing before a castle",
            "apply_appearance": False,
        },
    )
    assert resp.status_code == 200
    assert "Visual keywords" not in captured["prompt"]
    assert captured["prompt"] == "A valiant fighter standing before a castle"
