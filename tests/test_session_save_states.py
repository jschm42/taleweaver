"""Checkpoints as save states: automatic on scene/sequence change, /save, tw.save(), restore."""

from sqlalchemy import select

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.engine.interaction.trigger_service import TriggerService
from backend.engine.sessions.session_checkpoint_service import (
    MAX_CHECKPOINTS_PER_SESSION,
    REASON_MANUAL_SAVE,
    REASON_SCENE_CHANGE,
    REASON_SCRIPT_SAVE,
    REASON_SEQUENCE_CHANGE,
    SessionCheckpointService,
)
from backend.models.chat import ChatMessage
from backend.models.session_checkpoint import SessionCheckpoint
from backend.models.world_entity import WorldEntity, WorldScene
from tests.conftest import TestSessionLocal
from tests.test_game_loop import _seed_game_context


async def _checkpoints(db) -> list[SessionCheckpoint]:
    res = await db.execute(select(SessionCheckpoint).order_by(SessionCheckpoint.created_at))
    return list(res.scalars().all())


async def _messages(db) -> list[str]:
    res = await db.execute(select(ChatMessage.content).order_by(ChatMessage.created_at))
    return list(res.scalars().all())


async def test_save_command_creates_a_named_save_with_system_message():
    async with TestSessionLocal() as db:
        # Arrange
        user, _adv, _avatar, _state = await _seed_game_context(db)
        manager = GameTurnManager(db, "session-1", user)

        # Act
        chunks = [c async for c in manager.process_turn("/save Before the bridge")]

        # Assert
        checkpoints = await _checkpoints(db)
        assert [c.trigger_reason for c in checkpoints] == [REASON_MANUAL_SAVE]
        assert checkpoints[0].state_snapshot["label"] == "Before the bridge"
        assert any("Game saved: Before the bridge" in c for c in chunks)
        assert any(c.startswith("event: checkpoint") for c in chunks)
        assert "Game saved: Before the bridge" in await _messages(db)
        titles = [c.title for c in await SessionCheckpointService.list_checkpoints(db, "session-1")]
        assert titles == ["Save: Before the bridge"]


async def test_scene_and_sequence_change_queue_automatic_checkpoints():
    async with TestSessionLocal() as db:
        # Arrange
        user, adv, _avatar, state = await _seed_game_context(db)
        db.add(WorldScene(id="HALL", template_id=adv.id, label="Great Hall", description="."))
        await db.commit()
        manager = GameTurnManager(db, "session-1", user)
        await manager.initialize()
        manager.checkpoints.start_turn(manager.state)

        # Act
        manager.state.current_scene_id = "HALL"
        manager.state.active_sequence_id = "SEQ_2"
        events = await manager._persist_pending_checkpoints()
        again = await manager._persist_pending_checkpoints()

        # Assert
        reasons = sorted(c.trigger_reason for c in await _checkpoints(db))
        assert reasons == [REASON_SCENE_CHANGE, REASON_SEQUENCE_CHANGE]
        assert len(events) == 2
        assert again == []
        titles = {c.title for c in await SessionCheckpointService.list_checkpoints(db, "session-1")}
        assert "Checkpoint: Arrived at Great Hall" in titles


async def test_script_save_from_trigger_writes_save_and_message():
    async with TestSessionLocal() as db:
        # Arrange
        user, _adv, _avatar, _state = await _seed_game_context(db)
        manager = GameTurnManager(db, "session-1", user)
        await manager.initialize()

        # Act
        messages = await TriggerService.execute_trigger(
            db, manager.state, "on_enter_scene", "START", script_code="tw.save('Throne room')"
        )
        await db.commit()

        # Assert
        checkpoints = await _checkpoints(db)
        assert [c.trigger_reason for c in checkpoints] == [REASON_SCRIPT_SAVE]
        assert "Game saved: Throne room" in messages
        assert "Game saved: Throne room" in await _messages(db)


async def test_restore_brings_back_world_rows_sequence_and_removes_later_clones():
    async with TestSessionLocal() as db:
        # Arrange
        _user, adv, _avatar, state = await _seed_game_context(db)
        db.add(
            WorldEntity(
                id="CHEST",
                template_id=adv.id,
                session_id="session-1",
                entity_type="OBJECT",
                name="Chest",
                description="An oak chest.",
                current_scene_id="START",
                inventory=["GEM"],
            )
        )
        state.active_sequence_id = "SEQ_1"
        await db.commit()
        checkpoint = await SessionCheckpointService.create_checkpoint(
            db, "session-1", REASON_MANUAL_SAVE
        )
        await db.commit()

        chest = (
            await db.execute(select(WorldEntity).where(WorldEntity.id == "CHEST"))
        ).scalar_one()
        chest.inventory = []
        chest.current_scene_id = "VAULT"
        db.add(
            WorldEntity(
                id="CHEST_1",
                template_id=adv.id,
                session_id="session-1",
                entity_type="OBJECT",
                name="Chest",
                description="An oak chest.",
                current_scene_id="START",
            )
        )
        state.active_sequence_id = "SEQ_2"
        await db.commit()

        # Act
        await SessionCheckpointService.restore_checkpoint(db, "session-1", checkpoint.id)
        await db.commit()

        # Assert
        rows = (
            (await db.execute(select(WorldEntity).where(WorldEntity.session_id == "session-1")))
            .scalars()
            .all()
        )
        assert [(r.id, r.current_scene_id, r.inventory) for r in rows] == [
            ("CHEST", "START", ["GEM"])
        ]
        assert state.active_sequence_id == "SEQ_1"


async def test_saves_are_pruned_separately_from_automatic_checkpoints():
    async with TestSessionLocal() as db:
        # Arrange
        await _seed_game_context(db)

        # Act
        for _ in range(2):
            await SessionCheckpointService.create_checkpoint(db, "session-1", REASON_MANUAL_SAVE)
        for _ in range(MAX_CHECKPOINTS_PER_SESSION + 2):
            await SessionCheckpointService.create_checkpoint(db, "session-1", REASON_SCENE_CHANGE)
        await db.commit()

        # Assert
        reasons = [c.trigger_reason for c in await _checkpoints(db)]
        assert reasons.count(REASON_MANUAL_SAVE) == 2
        assert reasons.count(REASON_SCENE_CHANGE) == MAX_CHECKPOINTS_PER_SESSION
