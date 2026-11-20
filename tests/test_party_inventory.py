"""Handing items between the protagonist and the companion, and the companion's sheet page."""

import pytest

from backend.api.routes.adventures.companion_inventory import (
    GIVE,
    TAKE,
    transfer_companion_items,
)
from backend.api.routes.adventures.companion_sheet import build_companion_sheet
from backend.engine.interaction.command_parser import CommandParser
from backend.models.world_entity import WorldEntity
from tests.conftest import TestSessionLocal
from tests.test_party_follow import SESSION, _seed_turn_manager

TORCH = {"id": "TORCH", "name": "Torch", "item_type": "PICKABLE"}


async def _manager_with_torch(db):
    manager = await _seed_turn_manager(db)
    db.add(
        WorldEntity(
            id="TORCH",
            session_id=SESSION,
            entity_type="OBJECT",
            name="Torch",
            description="A burning torch.",
            item_type="PICKABLE",
            current_scene_id="__INVENTORY__",
            is_in_inventory=True,
        )
    )
    manager.avatar.inventory = [dict(TORCH)]
    await db.commit()
    return manager


@pytest.mark.asyncio
async def test_give_moves_the_item_to_the_companion_and_back(setup_test_db):
    # Arrange
    async with TestSessionLocal() as db:
        manager = await _manager_with_torch(db)

        # Act: hand the torch over
        given = await transfer_companion_items(manager, GIVE, "torch")

        # Assert
        assert given[-1] == ("system", "Lara now carries: Torch.")
        assert manager.avatar.inventory == []
        sheet = await build_companion_sheet(db, manager.state, {})
        assert [item["id"] for item in sheet["inventory"]] == ["TORCH"]

        # Act: take it back
        taken = await transfer_companion_items(manager, TAKE, "TORCH")

        # Assert
        assert any("Torch" in text for _, text in taken)
        assert [e["id"] for e in manager.avatar.inventory] == ["TORCH"]
        sheet = await build_companion_sheet(db, manager.state, {})
        assert sheet["inventory"] == []


@pytest.mark.asyncio
async def test_handover_needs_the_item_and_a_companion_nearby(setup_test_db):
    # Arrange
    async with TestSessionLocal() as db:
        manager = await _manager_with_torch(db)

        # Act
        missing = await transfer_companion_items(manager, TAKE, "torch")
        usage = await transfer_companion_items(manager, GIVE, "")
        manager.state.entity_states["LARA"] = {"current_scene_id": "CELLAR"}
        away = await transfer_companion_items(manager, GIVE, "torch")

        # Assert
        assert missing == [("system", "Lara doesn't carry torch.")]
        assert "Usage" in usage[0][1]
        assert away == [("system", "Lara is not here and cannot hear you.")]
        assert [e["id"] for e in manager.avatar.inventory] == ["TORCH"]


@pytest.mark.asyncio
async def test_companion_sheet_describes_the_active_companion(setup_test_db):
    # Arrange
    async with TestSessionLocal() as db:
        manager = await _seed_turn_manager(db)

        # Act
        sheet = await build_companion_sheet(db, manager.state, {"LARA": "/data/lara.png"})
        manager.state.entity_states = {}
        none = await build_companion_sheet(db, manager.state, {})

        # Assert
        assert sheet["id"] == "LARA" and sheet["name"] == "Lara"
        assert sheet["image_url"] == "/data/lara.png"
        assert sheet["present"] is True and sheet["following"] is True
        assert sheet["tactics"] == "BALANCED"
        assert "armor_class" in sheet["stats"]
        assert none is None


def test_transfer_commands_map_to_their_triggers():
    # Act / Assert
    give = CommandParser.parse_command(None, "/companion_give Torch")
    take = CommandParser.parse_command(None, "/companion_take Torch")
    assert give == "[TRIGGER_COMPANION_GIVE] Torch"
    assert take == "[TRIGGER_COMPANION_TAKE] Torch"
