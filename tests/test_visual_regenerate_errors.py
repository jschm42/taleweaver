"""Error reporting of POST /api/adventures/{id}/visuals/regenerate."""

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

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
