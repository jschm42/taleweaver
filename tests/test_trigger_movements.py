"""Scene triggers (e.g. on_enter_scene) apply NPC movements, teleports and story flags."""

import pytest
from sqlalchemy import select

from backend.engine.interaction.trigger_service import TriggerService
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldEntity, WorldScene
from tests.conftest import TestSessionLocal

SESSION = "sess_trigger_moves"


async def _seed(db) -> SessionState:
    db.add_all(
        [
            WorldScene(id="HALL", session_id=SESSION, label="Hall", description=""),
            WorldScene(id="LOCKED_ROOM", session_id=SESSION, label="Locked room", description=""),
            WorldEntity(
                id="UNIT_SEVEN",
                session_id=SESSION,
                entity_type="NPC",
                name="Unit Seven",
                description="A robot.",
                current_scene_id="HALL",
            ),
        ]
    )
    await db.commit()
    # The player has just entered the locked room when on_enter_scene fires.
    return SessionState(session_id=SESSION, current_scene_id="LOCKED_ROOM", entity_states={})


@pytest.mark.asyncio
async def test_move_to_player_in_enter_trigger_moves_the_npc(setup_test_db):
    # Arrange
    async with TestSessionLocal() as db:
        state = await _seed(db)

        # Act
        await TriggerService.execute_trigger(
            db,
            state,
            "on_enter_scene",
            "LOCKED_ROOM",
            script_code=(
                'tw.npcs.move_to_player("UNIT_SEVEN", "right in front of the player")\n'
                'tw.npcs.say("UNIT_SEVEN", "Don\'t mind me.")'
            ),
        )
        await db.commit()

    # Assert
    async with TestSessionLocal() as db:
        row = (
            await db.execute(select(WorldEntity).where(WorldEntity.session_id == SESSION))
        ).scalar_one()
        assert row.current_scene_id == "LOCKED_ROOM"
        assert row.spatial_position == "right in front of the player"
        assert state.entity_states["UNIT_SEVEN"]["current_scene_id"] == "LOCKED_ROOM"


@pytest.mark.asyncio
async def test_enter_trigger_applies_teleport_and_story_flags(setup_test_db):
    # Arrange
    async with TestSessionLocal() as db:
        state = await _seed(db)

        # Act
        await TriggerService.execute_trigger(
            db,
            state,
            "on_enter_scene",
            "LOCKED_ROOM",
            script_code="tw.flags.set('ROOM_SEEN', True)\ntw.scene.teleport('HALL')",
        )

    # Assert
    assert state.current_scene_id == "HALL"
    assert state.entity_states["__switch_story_flags__"]["ROOM_SEEN"] is True
