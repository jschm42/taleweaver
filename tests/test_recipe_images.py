"""CONSTRUCTABLE recipes never get an image: not on generation/import and not in exports."""

from types import SimpleNamespace

import pytest

from backend.engine.adventures.adventure_exporter import _serialize_world_entity
from backend.engine.manifest_apply.objects import _object_image
from backend.models.world_entity import WorldEntity

PLACEHOLDER = "/data/adventures/library/tpl/placeholder_recipe_abc123.svg"


@pytest.mark.asyncio
async def test_recipe_gets_no_image_even_when_the_manifest_has_one() -> None:
    # Arrange: the context is never touched for a recipe
    recipe = {"id": "RECIPE", "item_type": "CONSTRUCTABLE", "image_url": "assets/placeholder.svg"}

    # Act
    image_url = await _object_image(SimpleNamespace(), recipe, [], {}, (0, 1))

    # Assert
    assert image_url is None


@pytest.mark.parametrize(("item_type", "kept"), [("CONSTRUCTABLE", False), ("KEY", True)])
def test_export_drops_only_recipe_images(item_type, kept) -> None:
    # Arrange
    entity = WorldEntity(
        id="ENT", entity_type="OBJECT", name="Thing", item_type=item_type, image_url=PLACEHOLDER
    )

    # Act
    exported = _serialize_world_entity(entity)

    # Assert
    assert ("image_url" in exported) is kept
