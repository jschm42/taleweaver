"""Editing a take-locked item keeps its take-lock; only a type change drops a container lock."""

from unittest.mock import AsyncMock

from backend.api.routes.adventures.editing.entity_update.item import update_item
from backend.api.routes.adventures.editing.schemas import EntityUpdateRequest
from backend.models.world_entity import WorldEntity


def _item(item_type: str, locked: bool) -> WorldEntity:
    return WorldEntity(
        id="GOLDEN_WRENCH",
        template_id="tpl",
        entity_type="OBJECT",
        name="Golden Wrench",
        item_type=item_type,
        metadata_json={"locked": locked},
    )


async def _update(item: WorldEntity, **fields) -> None:
    payload = EntityUpdateRequest(target_type="object", target_id=item.id, **fields)
    await update_item(AsyncMock(), "tpl", AsyncMock(), item, payload)


async def test_unrelated_edit_keeps_the_take_lock() -> None:
    # Arrange
    item = _item("TOOL", locked=True)

    # Act
    await _update(item, reveal_rule="", description="Glittering at the bottom of the tank.")

    # Assert
    assert item.metadata_json["locked"] is True


async def test_take_lock_can_still_be_released() -> None:
    # Arrange
    item = _item("TOOL", locked=True)

    # Act
    await _update(item, locked=False)

    # Assert
    assert item.metadata_json["locked"] is False


async def test_container_turned_into_item_drops_its_lock() -> None:
    # Arrange: a locked chest becomes a plain item
    item = _item("CONTAINER", locked=True)

    # Act
    await _update(item, item_type="DEFAULT")

    # Assert
    assert "locked" not in item.metadata_json
