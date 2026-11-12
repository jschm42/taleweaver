"""The active companion follows the player on every scene change path."""

import pytest
from sqlalchemy import select

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.api.routes.adventures.manifest_export import serialize_exit
from backend.engine.interaction.trigger_service import TriggerService
from backend.engine.party import follow
from backend.engine.party.follow import bring_companion_along
from backend.engine.party.party_start import sync_starting_party_rows
from backend.engine.party.party_state import PARTY_KEY
from backend.engine.rules.rule_engine import EntityMovement, GameEvent
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio

SESSION = "sess_party_follow"
PARTY = {"active_id": "LARA", "recruited": ["LARA"], "following": True, "tactics": {}}


def _party_states(**overrides) -> dict:
    return {PARTY_KEY: {**PARTY, **overrides}}


async def _seed(db, *, companion_scene: str = "HALL", solo_exit: bool = False) -> SessionState:
    db.add_all(
        [
            WorldScene(id="HALL", session_id=SESSION, label="Hall", description=""),
            WorldScene(id="CELLAR", session_id=SESSION, label="Cellar", description=""),
            WorldExit(
                id="EXIT_HALL_CELLAR",
                session_id=SESSION,
                from_scene_id="HALL",
                to_scene_id="CELLAR",
                label="a narrow hatch",
                exit_type="bidirectional",
                companions_allowed=not solo_exit,
            ),
            WorldEntity(
                id="LARA",
                session_id=SESSION,
                entity_type="NPC",
                name="Lara",
                description="A rogue.",
                current_scene_id=companion_scene,
                spatial_position="by the door",
            ),
        ]
    )
    await db.commit()
    return SessionState(session_id=SESSION, current_scene_id="HALL", entity_states=_party_states())


async def _lara(db) -> WorldEntity:
    res = await db.execute(
        select(WorldEntity).where(WorldEntity.session_id == SESSION, WorldEntity.id == "LARA")
    )
    return res.scalar_one()


async def test_companion_follows_into_the_new_scene(setup_test_db):
    # Arrange
    async with TestSessionLocal() as db:
        state = await _seed(db)
        state.current_scene_id = "CELLAR"

        # Act
        messages = await bring_companion_along(db, state, "HALL")
        await db.commit()

        # Assert
        assert messages == []
        assert state.entity_states["LARA"]["current_scene_id"] == "CELLAR"
        assert state.entity_states["LARA"]["spatial_position"] is None
        assert (await _lara(db)).current_scene_id == "CELLAR"


async def test_solo_exit_leaves_the_companion_behind(setup_test_db):
    # Arrange
    async with TestSessionLocal() as db:
        state = await _seed(db, solo_exit=True)
        world_exit = await db.get(WorldExit, "EXIT_HALL_CELLAR")
        state.current_scene_id = "CELLAR"

        # Act
        messages = await bring_companion_along(db, state, "HALL", world_exit=world_exit)

        # Assert
        assert messages == ["Lara cannot follow you here and stays behind."]
        assert "LARA" not in state.entity_states
        assert (await _lara(db)).current_scene_id == "HALL"


async def test_solo_sequence_leaves_the_companion_behind(setup_test_db, monkeypatch):
    # Arrange
    async def solo_sequence(db, state, adventure=None):
        return {"id": "SEQ_1", "companions_allowed": False}

    monkeypatch.setattr(follow, "_active_sequence", solo_sequence)
    async with TestSessionLocal() as db:
        state = await _seed(db)
        state.current_scene_id = "CELLAR"

        # Act
        messages = await bring_companion_along(db, state, "HALL")

        # Assert
        assert len(messages) == 1
        assert (await _lara(db)).current_scene_id == "HALL"


async def test_companion_elsewhere_or_waiting_does_not_follow(setup_test_db):
    # Arrange
    async with TestSessionLocal() as db:
        state = await _seed(db, companion_scene="CELLAR")

        # Act: the companion is not in the scene the player left
        state.current_scene_id = "CELLAR"
        elsewhere = await bring_companion_along(db, state, "HALL")
        # Act: the party does not follow
        state.entity_states = _party_states(following=False)
        state.current_scene_id = "HALL"
        waiting = await bring_companion_along(db, state, "CELLAR")

        # Assert
        assert elsewhere == [] and waiting == []
        assert (await _lara(db)).current_scene_id == "CELLAR"


async def test_defeated_companion_does_not_follow(setup_test_db):
    # Arrange
    async with TestSessionLocal() as db:
        state = await _seed(db)
        state.entity_states = {**_party_states(), "LARA": {"is_defeated": True}}
        state.current_scene_id = "CELLAR"

        # Act
        await bring_companion_along(db, state, "HALL")

        # Assert
        assert (await _lara(db)).current_scene_id == "HALL"


async def test_script_teleport_takes_the_companion_along(setup_test_db):
    # Arrange
    async with TestSessionLocal() as db:
        state = await _seed(db)

        # Act
        await TriggerService.execute_trigger(
            db, state, "on_interact", "LEVER", script_code="tw.scene.teleport('CELLAR')"
        )
        await db.commit()

        # Assert
        assert state.current_scene_id == "CELLAR"
        assert state.entity_states["LARA"]["current_scene_id"] == "CELLAR"
        assert (await _lara(db)).current_scene_id == "CELLAR"


async def _seed_turn_manager(db) -> GameTurnManager:
    user = User(username="party_player", hashed_password="pw", role="user")
    adv = AdventureTemplate(id="adv-party", title="Party", owner_id="admin", strict_rules=True)
    db.add_all([user, adv])
    await db.flush()
    avatar = Avatar(id="av-party", template_id=adv.id, user_id=user.id, name="Hero", hp=50)
    db.add(avatar)
    state = await _seed(db)
    state.template_id = adv.id
    state.avatar_id = avatar.id
    state.user_id = user.id
    state.in_game_time = 0
    db.add(state)
    await db.commit()
    manager = GameTurnManager(db=db, game_id=SESSION, user=user)
    manager.state = state
    manager.adventure = adv
    manager.avatar = avatar
    return manager


async def test_gm_scene_transition_takes_the_companion_along(setup_test_db):
    # Arrange
    async with TestSessionLocal() as db:
        manager = await _seed_turn_manager(db)

        # Act
        await manager._apply_game_event(GameEvent(new_scene_id="CELLAR"))
        await db.commit()

        # Assert
        assert manager.state.current_scene_id == "CELLAR"
        assert manager.state.entity_states["LARA"]["current_scene_id"] == "CELLAR"
        assert manager.state.entity_states[PARTY_KEY]["active_id"] == "LARA"
        assert (await _lara(db)).current_scene_id == "CELLAR"


async def test_gm_cannot_move_the_following_companion_away(setup_test_db):
    # Arrange
    async with TestSessionLocal() as db:
        manager = await _seed_turn_manager(db)
        event = GameEvent(
            moved_entities=[
                EntityMovement(entity_id="LARA", to_scene_id="CELLAR"),
                EntityMovement(entity_id="LARA", to_scene_id="HALL", to_spatial_position="left"),
            ]
        )

        # Act
        violations = await manager.guardrails._enforce_npc_movement_guardrails(event)

        # Assert: the scene move is dropped silently, a position change in place stays
        assert violations == []
        assert [m.to_scene_id for m in event.moved_entities] == ["HALL"]


async def test_starting_companion_row_moves_to_the_start_scene(setup_test_db):
    # Arrange
    async with TestSessionLocal() as db:
        await _seed(db)
        states = {**_party_states(), "LARA": {"current_scene_id": "CELLAR"}}

        # Act
        await sync_starting_party_rows(db, SESSION, states)
        await db.commit()

        # Assert
        assert (await _lara(db)).current_scene_id == "CELLAR"


async def test_exit_export_keeps_companions_allowed(setup_test_db):
    # Arrange
    async with TestSessionLocal() as db:
        await _seed(db, solo_exit=True)

        # Act
        exported = serialize_exit(await db.get(WorldExit, "EXIT_HALL_CELLAR"))

        # Assert
        assert exported["companions_allowed"] is False
