"""Changing an item's type in the editor resets its type-derived discovery visibility."""

from unittest.mock import AsyncMock

from backend.api.routes.adventures.editing.entity_update.item import update_item
from backend.api.routes.adventures.editing.schemas import EntityUpdateRequest
from backend.models.world_entity import WorldEntity

IMPORTED_SWITCH_VISIBILITY = {
    "mentioned_in_scene": True,
    "listed_in_discoveries": False,
    "lootable": False,
}


def _imported_switch() -> WorldEntity:
    return WorldEntity(
        id="MICROWAVE",
        template_id="tpl",
        entity_type="OBJECT",
        name="Microwave",
        item_type="SWITCH",
        metadata_json={
            "discovery_visibility": dict(IMPORTED_SWITCH_VISIBILITY),
            "switch": {"states": ["OFF", "ON"], "initial_state": "OFF"},
        },
    )


async def test_switch_to_container_switch_drops_stored_visibility() -> None:
    # Arrange
    item = _imported_switch()
    payload = EntityUpdateRequest(
        target_type="object", target_id="MICROWAVE", item_type="CONTAINER_SWITCH"
    )

    # Act
    await update_item(AsyncMock(), "tpl", AsyncMock(), item, payload)

    # Assert
    assert item.item_type == "CONTAINER_SWITCH"
    assert "discovery_visibility" not in item.metadata_json
    assert item.metadata_json["switch"]["states"] == ["OFF", "ON"]


async def test_update_without_type_change_keeps_stored_visibility() -> None:
    # Arrange
    item = _imported_switch()
    payload = EntityUpdateRequest(
        target_type="object", target_id="MICROWAVE", description="A humming microwave."
    )

    # Act
    await update_item(AsyncMock(), "tpl", AsyncMock(), item, payload)

    # Assert
    assert item.metadata_json["discovery_visibility"] == IMPORTED_SWITCH_VISIBILITY
