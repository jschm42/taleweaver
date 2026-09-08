# pyright: reportUnusedParameter=false, reportUnusedVariable=false, reportUnreachable=false
# pylint: disable=unused-argument,unused-variable,using-constant-test
# ruff: noqa: ARG001,F841,PLR0133

from unittest.mock import AsyncMock, MagicMock
from types import SimpleNamespace
import pytest
from sqlalchemy import select

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.engine.rule_engine import EntityMovement, GameEvent, WorldEntityUpdate
from backend.engine.memory_manager import MemoryManager
from backend.engine.debug_engine import DebugEngine
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldScene

pytestmark = pytest.mark.asyncio


async def _seed_test_context(db):
    user = User(username="player_npc_test", hashed_password="pw", role="user")
    adv = AdventureTemplate(
        id="adv-npc-test",
        title="NPC Test Adventure",
        owner_id="admin",
        time_per_turn=5,
        strict_rules=True
    )
    db.add_all([user, adv])
    await db.flush()

    avatar = Avatar(
        id="av-npc-test",
        template_id=adv.id,
        user_id=user.id,
        name="Hero",
        role="Warrior",
        hp=100,
        stats={"strength": 10, "dexterity": 10}
    )
    db.add(avatar)
    await db.flush()

    scene_a = WorldScene(
        id="SCENE_A",
        template_id=adv.id,
        session_id="session-npc-test",
        label="Scene A",
        description="First room"
    )
    scene_b = WorldScene(
        id="SCENE_B",
        template_id=adv.id,
        session_id="session-npc-test",
        label="Scene B",
        description="Second room"
    )
    scene_c = WorldScene(
        id="SCENE_C",
        template_id=adv.id,
        session_id="session-npc-test",
        label="Scene C",
        description="Third room"
    )
    db.add_all([scene_a, scene_b, scene_c])

    # Stationary NPC
    npc_stat = WorldEntity(
        id="NPC_STAT",
        session_id="session-npc-test",
        template_id=None,
        entity_type="NPC",
        name="Statue Guard",
        description="A stationary guard",
        current_scene_id="SCENE_A",
        spatial_position="by the gate",
        moveable=False,
        allowed_scenes=[],
        notes="is standing still"
    )

    # Moveable NPC with allowed scenes
    npc_mov = WorldEntity(
        id="NPC_MOV",
        session_id="session-npc-test",
        template_id=None,
        entity_type="NPC",
        name="Wandering Merchant",
        description="A traveling peddler",
        current_scene_id="SCENE_A",
        spatial_position="in the center",
        moveable=True,
        allowed_scenes=["SCENE_A", "SCENE_B"],
        notes="is looking for bargains"
    )

    # Free Roaming NPC
    npc_free = WorldEntity(
        id="NPC_FREE",
        session_id="session-npc-test",
        template_id=None,
        entity_type="NPC",
        name="Wild Wolf",
        description="A wild beast",
        current_scene_id="SCENE_A",
        moveable=True,
        allowed_scenes=[],
        notes=None
    )

    db.add_all([npc_stat, npc_mov, npc_free])
    await db.flush()

    state = SessionState(
        session_id="session-npc-test",
        template_id=adv.id,
        avatar_id=avatar.id,
        user_id=user.id,
        current_scene_id="SCENE_A",
        in_game_time=0,
        entity_states={}
    )
    db.add(state)
    await db.commit()
    return user, adv, avatar, state


async def test_npc_movement_guardrails(setup_test_db):
    """Verifies that moveable=False and allowed_scenes are strictly enforced by guardrails."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, adv, avatar, state = await _seed_test_context(db)
        manager = GameTurnManager(db=db, game_id=state.session_id, user=user)
        manager.state = state
        manager.adventure = adv
        manager.avatar = avatar

        # 1. Attempt to move stationary NPC to SCENE_B -> Should be blocked
        event_stat = GameEvent(
            narrative_description="",
            moved_entities=[
                EntityMovement(entity_id="NPC_STAT", to_scene_id="SCENE_B")
            ]
        )
        violations = await manager.guardrails._enforce_npc_movement_guardrails(event_stat)
        assert len(violations) == 1
        assert "not moveable and cannot change scenes" in violations[0]
        assert len(event_stat.moved_entities) == 0

        # 2. Stationary NPC changing position within same scene -> Allowed
        event_same_scene = GameEvent(
            narrative_description="",
            moved_entities=[
                EntityMovement(entity_id="NPC_STAT", to_scene_id="SCENE_A", to_spatial_position="at the fountain")
            ]
        )
        violations = await manager.guardrails._enforce_npc_movement_guardrails(event_same_scene)
        assert len(violations) == 0
        assert len(event_same_scene.moved_entities) == 1

        # 3. Moveable NPC moving to allowed scene (SCENE_B) -> Allowed
        event_mov_allowed = GameEvent(
            narrative_description="",
            moved_entities=[
                EntityMovement(entity_id="NPC_MOV", to_scene_id="SCENE_B")
            ]
        )
        violations = await manager.guardrails._enforce_npc_movement_guardrails(event_mov_allowed)
        assert len(violations) == 0
        assert len(event_mov_allowed.moved_entities) == 1

        # 4. Moveable NPC moving to restricted scene (SCENE_C) -> Blocked
        event_mov_blocked = GameEvent(
            narrative_description="",
            moved_entities=[
                EntityMovement(entity_id="NPC_MOV", to_scene_id="SCENE_C")
            ]
        )
        violations = await manager.guardrails._enforce_npc_movement_guardrails(event_mov_blocked)
        assert len(violations) == 1
        assert "not permitted to move to scene 'SCENE_C'" in violations[0]
        assert len(event_mov_blocked.moved_entities) == 0

        # 5. Free-roaming NPC (allowed_scenes=[]) moving to SCENE_C -> Allowed
        event_free = GameEvent(
            narrative_description="",
            moved_entities=[
                EntityMovement(entity_id="NPC_FREE", to_scene_id="SCENE_C")
            ]
        )
        violations = await manager.guardrails._enforce_npc_movement_guardrails(event_free)
        assert len(violations) == 0
        assert len(event_free.moved_entities) == 1


async def test_npc_notes_update_and_prompt_formatting(setup_test_db):
    """Verifies that the GM can update NPC notes in session state, and they appear in prompt context."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, adv, avatar, state = await _seed_test_context(db)
        manager = GameTurnManager(db=db, game_id=state.session_id, user=user)
        manager.state = state
        manager.adventure = adv
        manager.avatar = avatar

        # Update notes via updated_entities
        event = GameEvent(
            narrative_description="The merchant is badly hurt after a brawl.",
            updated_entities=[
                WorldEntityUpdate(
                    entity_id="NPC_MOV",
                    notes="is badly hurt, very angry because joe does not like him"
                )
            ]
        )
        await manager.state_applier._apply_game_event(event)

        # Check session entity_states override
        assert state.entity_states["NPC_MOV"]["notes"] == "is badly hurt, very angry because joe does not like him"

        # Check format_location_context includes notes and movement
        ent_res = await db.execute(select(WorldEntity).where(WorldEntity.session_id == state.session_id))
        all_ents = ent_res.scalars().all()
        # Apply overrides
        for e in all_ents:
            if e.id in state.entity_states:
                if "notes" in state.entity_states[e.id]:
                    e.notes = state.entity_states[e.id]["notes"]

        scene_a = (await db.execute(select(WorldScene).where(WorldScene.id == "SCENE_A"))).scalar_one()
        loc_ctx = MemoryManager._build_location_context(
            current_scene=scene_a,
            entities=all_ents,
            exits=[],
            detail_level="full"
        )
        assert "Status/Notes: \"is badly hurt, very angry because joe does not like him\"" in loc_ctx
        assert "Movable: Allowed in SCENE_A, SCENE_B" in loc_ctx
        assert "Stationary" in loc_ctx


async def test_debug_commands_for_npc_notes_and_moveable(setup_test_db):
    """Verifies /debug npc_note and /debug moveable sub-commands."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, adv, avatar, state = await _seed_test_context(db)

        # Set note via debug command
        res_note = await DebugEngine.handle_debug_command(
            db, state, "npc_note NPC_STAT is badly hurt"
        )
        assert "notes set to: \"is badly hurt\"" in res_note
        assert state.entity_states["NPC_STAT"]["notes"] == "is badly hurt"

        # Toggle moveable via debug command
        res_mov = await DebugEngine.handle_debug_command(
            db, state, "moveable NPC_STAT true"
        )
        assert "moveable set to True" in res_mov
        assert state.entity_states["NPC_STAT"]["moveable"] is True
