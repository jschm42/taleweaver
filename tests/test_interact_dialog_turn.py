"""A full turn that names an NPC fires its on_interact script, and a dialog it opens stays open."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.engine.rules.rule_engine import GameEvent
from backend.engine.scripting.dialog import pending_dialog
from backend.models.world_entity import WorldEntity
from tests.conftest import TestSessionLocal
from tests.test_game_loop import _seed_game_context

_OPEN_TREE = """
tw.vars.set('talked', True)
tw.dialog.tree({
    'npc_id': 'GARGOYLE',
    'nodes': {'root': {'npc_text': 'Another apprentice.', 'responses': [
        {'text': 'Tell me the riddle.', 'next_node': None},
    ]}},
}, speaker='Grimsby the Gargoyle')
"""


def _mock_llm(monkeypatch) -> None:
    llm = MagicMock()
    llm.aexecute_complex_task = AsyncMock(return_value=GameEvent(narrative_description="Hm."))

    async def stream(*_args, **_kwargs):
        yield MagicMock(choices=[MagicMock(delta=MagicMock(content="The gargoyle sneers."))])

    llm.stream_simple_task = AsyncMock(return_value=stream())
    monkeypatch.setattr(
        "backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *a, **k: llm
    )


@pytest.mark.asyncio
async def test_talking_to_an_npc_opens_its_dialog_tree(setup_test_db, monkeypatch):
    async with TestSessionLocal() as db:
        # Arrange
        user, _adv, _avatar, state = await _seed_game_context(db)
        db.add(
            WorldEntity(
                id="GARGOYLE",
                session_id=state.session_id,
                entity_type="NPC",
                name="Grimsby the Gargoyle",
                description="A stone bust.",
                current_scene_id=state.current_scene_id,
                is_hidden=False,
                is_in_inventory=False,
                metadata_json={"on_interact_script": _OPEN_TREE},
            )
        )
        await db.commit()
        _mock_llm(monkeypatch)
        manager = GameTurnManager(db, state.session_id, user)

        # Act
        _chunks = [chunk async for chunk in manager.process_turn("talk to grimsby")]

        # Assert
        await db.refresh(state)
        assert (state.entity_states or {}).get("__script_vars__", {}).get("talked") is True
        assert pending_dialog(state.entity_states) is not None


@pytest.mark.asyncio
async def test_greeting_an_npc_fires_its_on_interact_script(setup_test_db, monkeypatch):
    """The context menu's /greet command counts as an interaction with the greeted NPC."""
    async with TestSessionLocal() as db:
        # Arrange
        user, _adv, _avatar, state = await _seed_game_context(db)
        db.add(
            WorldEntity(
                id="GARGOYLE",
                session_id=state.session_id,
                entity_type="NPC",
                name="Grimsby the Gargoyle",
                description="A stone bust.",
                current_scene_id=state.current_scene_id,
                is_hidden=False,
                is_in_inventory=False,
                metadata_json={"on_interact_script": "tw.vars.set('greeted', True)"},
            )
        )
        await db.commit()
        _mock_llm(monkeypatch)
        manager = GameTurnManager(db, state.session_id, user)

        # Act
        _chunks = [chunk async for chunk in manager.process_turn("/greet Grimsby the Gargoyle")]

        # Assert
        await db.refresh(state)
        assert (state.entity_states or {}).get("__script_vars__", {}).get("greeted") is True
