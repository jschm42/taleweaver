"""Orders to the companion (stay here / follow me) and the COMPANION prompt block."""

import pytest

from backend.api.routes.adventures.companion_command import companion_order_command
from backend.engine.party.orders import apply_order, give_companion_order
from backend.engine.party.party_prompt import companion_prompt_block
from backend.engine.party.party_state import PARTY_KEY, read_party
from backend.engine.party.party_view import mark_active_companion
from backend.engine.rules.rule_engine import GameEvent
from backend.models.world_entity import WorldEntity
from tests.conftest import TestSessionLocal
from tests.test_party_follow import _lara, _seed, _seed_turn_manager

LABELS = {"HALL": "Hall", "CELLAR": "Cellar"}


def _row(scene: str = "HALL", **meta) -> WorldEntity:
    return WorldEntity(
        id="LARA", entity_type="NPC", name="Lara", current_scene_id=scene, metadata_json=meta
    )


def _states(following: bool = True) -> dict:
    return {PARTY_KEY: {"active_id": "LARA", "recruited": ["LARA"], "following": following}}


def test_wait_and_follow_switch_the_party_flag():
    # Arrange
    states = _states()

    # Act
    waited = apply_order(states, _row(), "wait", "HALL")
    again = apply_order(states, _row(), "wait", "HALL")
    followed = apply_order(states, _row(), "follow", "HALL")

    # Assert
    assert waited.applied and waited.message == "Lara stays here and waits for you."
    assert not again.applied and "already waiting" in again.message
    assert followed.applied and read_party(states).following is True


def test_orders_need_a_companion_who_is_here_and_standing():
    # Arrange
    states = _states(following=False)
    states["LARA"] = {"current_scene_id": "CELLAR"}

    # Act
    away = apply_order(states, _row(), "follow", "HALL")
    states["LARA"] = {"current_scene_id": "HALL", "is_defeated": True}
    defeated = apply_order(states, _row(), "follow", "HALL")

    # Assert
    assert not away.applied and "not here" in away.message
    assert not defeated.applied
    assert read_party(states).following is False


def test_prompt_block_tells_both_passes_about_the_companion():
    # Arrange
    states = _states()
    rows = [_row(companion={"banter": "CHATTY"})]

    # Act
    mechanics = companion_prompt_block(states, rows, "HALL", LABELS, for_mechanics=True)
    narration = companion_prompt_block(states, rows, "HALL", LABELS, for_mechanics=False)
    away = companion_prompt_block(states, [_row("CELLAR")], "HALL", LABELS, for_mechanics=False)

    # Assert
    assert "COMPANION: Lara (ID LARA)" in mechanics and "companion_order" in mechanics
    assert "often adds short remarks" in narration
    assert "waits in Cellar" in away and "Do not let it speak" in away
    assert companion_prompt_block({}, rows, "HALL", LABELS, for_mechanics=True) == ""


def test_entity_payload_carries_the_following_flag():
    # Arrange
    entities = [{"id": "LARA"}]

    # Act
    mark_active_companion(entities, _states(following=False))

    # Assert
    assert entities[0] == {"id": "LARA", "is_companion": True, "companion_following": False}


@pytest.mark.asyncio
async def test_companion_command_applies_the_order_and_asks_for_a_reaction(setup_test_db):
    # Arrange
    async with TestSessionLocal() as db:
        state = await _seed(db)
        manager = type("Manager", (), {"db": db, "state": state})()

        # Act
        outcome = await companion_order_command(manager, "wait")
        usage = await companion_order_command(manager, "dance")

        # Assert
        assert outcome.events == [("system", "Lara stays here and waits for you.")]
        assert outcome.reaction_prompt.startswith("[COMPANION_ORDER]")
        assert read_party(state.entity_states).following is False
        assert usage.reaction_prompt is None and "Usage" in usage.events[0][1]


@pytest.mark.asyncio
async def test_gm_order_to_wait_applies_before_the_scene_change(setup_test_db):
    # Arrange: the player says "Lara, stay here" and walks into the cellar in one message
    async with TestSessionLocal() as db:
        manager = await _seed_turn_manager(db)

        # Act
        await manager._apply_game_event(GameEvent(companion_order="wait", new_scene_id="CELLAR"))
        await db.commit()

        # Assert: the player moved, Lara stayed behind and waits
        assert manager.state.current_scene_id == "CELLAR"
        assert (await _lara(db)).current_scene_id == "HALL"
        assert read_party(manager.state.entity_states).following is False


@pytest.mark.asyncio
async def test_follow_order_does_not_reach_a_companion_elsewhere(setup_test_db):
    # Arrange
    async with TestSessionLocal() as db:
        state = await _seed(db, companion_scene="CELLAR")
        state.entity_states[PARTY_KEY]["following"] = False

        # Act
        result = await give_companion_order(db, state, "follow")

        # Assert
        assert not result.applied
        assert read_party(state.entity_states).following is False
