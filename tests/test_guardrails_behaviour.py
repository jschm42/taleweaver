"""Behaviour introduced by the guardrails refactor (language independence, unified unlock engine)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.engine.rules.rule_engine import GameEvent, WorldEntityUpdate
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene
from tests.conftest import TestSessionLocal
from tests.test_game_loop import _seed_game_context

pytestmark = pytest.mark.asyncio


def _intent_llm(monkeypatch, target: str) -> MagicMock:
    llm = MagicMock()
    llm.aexecute_simple_task = AsyncMock(return_value=f'{{"action":"search","target":"{target}"}}')
    llm.aexecute_complex_task = AsyncMock(side_effect=RuntimeError("no LLM in tests"))
    monkeypatch.setattr(
        "backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *a, **k: llm
    )
    return llm


async def _manager_with_far_trashcan(db):
    user, _adv, _avatar, state = await _seed_game_context(db)
    db.add(WorldScene(id="NEXT", session_id=state.session_id, label="Alley", description="Dark."))
    db.add(WorldEntity(id="TRASHCAN", session_id=state.session_id, entity_type="OBJECT", name="trashcan",
                       description="Rusty.", current_scene_id="NEXT", is_hidden=False, is_in_inventory=False))  # fmt: skip
    await db.commit()
    manager = GameTurnManager(db, state.session_id, user)
    await manager.initialize()
    return manager


@pytest.mark.parametrize("generic_target", ["la pièce", "das Zimmer", "la habitación"])
async def test_generic_area_targets_pass_in_any_language(
    setup_test_db, monkeypatch, generic_target
):
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _manager_with_far_trashcan(db)
        _intent_llm(monkeypatch, generic_target)

        # Act
        blocked = await manager._guard_non_visible_inspect_or_search(
            f"je fouille {generic_target} (trashcan?)"
        )

        # Assert
        assert blocked is None


async def test_unreachable_known_entity_is_still_blocked(setup_test_db, monkeypatch):
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _manager_with_far_trashcan(db)
        _intent_llm(monkeypatch, "trashcan")

        # Act
        blocked = await manager._guard_non_visible_inspect_or_search(
            "je fouille la poubelle trashcan"
        )

        # Assert
        assert blocked and "cannot inspect or search 'trashcan'" in blocked


async def test_inventory_container_honours_unlock_expression_and_failure_text(setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange
        user, _adv, avatar, state = await _seed_game_context(db)
        avatar.inventory = [{
            "id": "MUSIC_BOX", "name": "Music Box", "item_type": "CONTAINER", "locked": True,
            "metadata_json": {"unlock_expression": "tw.vars.get('tune_known') == True",
                              "on_unlock_failure_text": "The box hums a wrong note."},
        }]  # fmt: skip
        await db.commit()
        manager = GameTurnManager(db, state.session_id, user)
        await manager.initialize()
        event = GameEvent(updated_entities=[WorldEntityUpdate(entity_id="MUSIC_BOX", locked=False)])

        # Act
        reasons = await manager._enforce_container_unlock_guardrails(event, "open the music box")

        # Assert
        assert reasons == ["The box hums a wrong note."]
        assert any(
            up.entity_id == "MUSIC_BOX" and up.locked is True for up in event.updated_entities
        )


async def test_scene_container_message_does_not_leak_item_id(setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange
        user, _adv, _avatar, state = await _seed_game_context(db)
        db.add(WorldEntity(id="SAFE", session_id=state.session_id, entity_type="OBJECT", item_type="CONTAINER",
                           name="Safe", description="Steel.", current_scene_id=state.current_scene_id,
                           metadata_json={"item_to_unlock": "SECRET_KEY_7", "locked": True}))  # fmt: skip
        await db.commit()
        manager = GameTurnManager(db, state.session_id, user)
        await manager.initialize()
        event = GameEvent(updated_entities=[WorldEntityUpdate(entity_id="SAFE", locked=False)])

        # Act
        reasons = await manager._enforce_container_unlock_guardrails(event, "open the safe")

        # Assert
        assert reasons == ["You need a specific item to unlock Safe."]


async def test_reversed_bidirectional_exit_honours_unlock_expression(setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange: the exit is stored START -> NEXT, the player stands in NEXT and walks back.
        user, _adv, _avatar, state = await _seed_game_context(db)
        db.add(
            WorldScene(id="NEXT", session_id=state.session_id, label="Alley", description="Dark.")
        )
        db.add(WorldExit(session_id=state.session_id, from_scene_id="START", to_scene_id="NEXT", label="Iron gate",
                         exit_type="bidirectional", is_locked=True,
                         unlock_expression="tw.vars.get('gate_open') == True"))  # fmt: skip
        state.current_scene_id = "NEXT"
        await db.commit()
        manager = GameTurnManager(db, state.session_id, user)
        await manager.initialize()
        event = GameEvent(new_scene_id="START")

        # Act
        reasons = await manager._enforce_exit_unlock_guardrails(
            event, "go back through the iron gate"
        )

        # Assert
        assert reasons
        assert event.new_scene_id is None
