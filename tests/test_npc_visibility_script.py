"""Scripts take NPCs out of the story and bring them back: tw.npcs.hide/reveal, npc.hide()."""

import pytest

from backend.api.routes.adventures.logic import AdventureLogic
from tests.conftest import TestSessionLocal
from tests.test_talents import _seed_world


async def _scene_npc_ids(manager) -> set[str]:
    entities = await AdventureLogic.build_session_entities(manager.db, manager.state)
    return {e["id"] for e in entities if e.get("entity_type") == "NPC"}


@pytest.mark.asyncio
async def test_hidden_npc_leaves_the_scene_and_reveal_brings_it_back(setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _seed_world(db)

        # Act
        await manager._execute_inline_script(
            "tw.vars.set('hidden_ok', tw.npcs.hide('GUARD'))\n"
            "tw.vars.set('unknown', tw.npcs.hide('NOBODY'))",
            "test",
            "GUARD",
        )
        await db.flush()
        hidden_ids = await _scene_npc_ids(manager)
        target_while_hidden = await manager._find_scene_npc_by_hint("guard")
        await manager._execute_inline_script("tw.npcs.get('GUARD').reveal()", "test", "GUARD")
        await db.flush()

        # Assert
        script_vars = manager.state.entity_states["__script_vars__"]
        assert script_vars == {**script_vars, "hidden_ok": True, "unknown": False}
        assert "GUARD" not in hidden_ids
        assert target_while_hidden is None
        assert "GUARD" in await _scene_npc_ids(manager)
        assert (await manager._find_scene_npc_by_hint("guard")) is not None


@pytest.mark.asyncio
async def test_npc_proxy_hide_reports_hidden_state(setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _seed_world(db)

        # Act
        await manager._execute_inline_script(
            "guard = tw.npcs.get('GUARD')\nguard.hide()\ntw.vars.set('now_hidden', guard.is_hidden)",
            "test",
            "GUARD",
        )

        # Assert
        assert manager.state.entity_states["__script_vars__"]["now_hidden"] is True
