"""Nested NPC dialogues: tw.dialog.tree opens a node, each choice walks the tree."""

import pytest
from sqlalchemy import select

from backend.api.routes.adventures.dialog_service import DialogChoiceResolver
from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.core.dialog_validator import dialog_handlers
from backend.engine.scripting.context import GameContext
from backend.engine.scripting.dialog import client_dialog, pending_dialog
from backend.engine.scripting.dialog_tree import normalize_tree
from backend.engine.scripting.runner import ScriptRunner
from backend.models.chat import ChatMessage
from tests.conftest import TestSessionLocal
from tests.test_game_loop import _seed_game_context

INIT_SCRIPT = """
GORAN = {
    "dialogue_id": "goran_intro",
    "initial_node": "root",
    "nodes": {
        "root": {
            "npc_text": "What do you want?",
            "responses": [
                {"text": "Gear for the wild.", "next_node": "equipment"},
                {"text": "Rumours about the mine?", "next_node": "root", "once": True,
                 "script": "tw.vars.set('asked_mine', True)"},
                {"text": "Bye.", "next_node": None},
            ],
        },
        "equipment": {
            "npc_text": "Good iron costs good gold.",
            "responses": [
                {"text": "I take the sword. [250 Gold]",
                 "condition": "tw.vars.get('gold', 0) >= 250",
                 "action": "BUY_SWORD", "next_node": "equipment"},
                {"text": "Too expensive.", "next_node": "root"},
            ],
        },
    },
}

def on_goran_action(action):
    tw.vars.set('last_action', action)

def on_goran_end(path):
    tw.vars.set('goran_path', [step['node'] + ':' + str(step['response']) for step in path])
"""
OPEN_TREE = (
    "tw.dialog.tree(GORAN, on_end='on_goran_end', on_action=on_goran_action, speaker='Goran')"
)


def _run(code: str, context: GameContext) -> None:
    ScriptRunner([], init_script=INIT_SCRIPT).execute_code(code, {"tw": context, "game": context})


async def _manager(db, gold: int = 0) -> GameTurnManager:
    user, adv, _avatar, state = await _seed_game_context(db)
    adv.original_manifest = {"init_script": INIT_SCRIPT}
    state.entity_states = {"__script_vars__": {"gold": gold}}
    await db.commit()
    manager = GameTurnManager(db, "session-1", user)
    await manager.initialize()
    await manager._execute_inline_script(OPEN_TREE, "on_interact", "GORAN")
    await db.commit()
    return manager


async def _answer(manager: GameTurnManager, label_start: str) -> dict:
    dialog = pending_dialog(manager.state.entity_states)
    option = next(o for o in dialog["options"] if o["label"].startswith(label_start))
    return await DialogChoiceResolver(manager).resolve(dialog["id"], option["index"], None)


def _vars(manager: GameTurnManager) -> dict:
    return manager.state.entity_states.get("__script_vars__", {})


def test_tree_opens_initial_node_and_hides_server_data():
    # Arrange
    context = GameContext()

    # Act
    _run(OPEN_TREE, context)

    # Assert
    dialog = context.changeset.pending_dialog
    assert dialog["kind"] == "tree"
    assert dialog["node"] == "root"
    assert dialog["prompt"] == "What do you want?"
    assert dialog["speaker"] == "Goran"
    payload = client_dialog(dialog)
    assert set(payload) == {"id", "prompt", "speaker", "options"}
    assert [o["index"] for o in payload["options"]] == [0, 1, 2]


def test_tree_with_dangling_node_is_rejected():
    # Arrange
    tree = {"nodes": {"a": {"npc_text": "Hi", "responses": [{"text": "x", "next_node": "b"}]}}}

    # Act
    normalized, problem = normalize_tree(tree)

    # Assert
    assert normalized is None
    assert "b" in problem


@pytest.mark.asyncio
async def test_tree_walk_runs_scripts_hides_once_and_calls_on_end():
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _manager(db)

        # Act
        first = await _answer(manager, "Rumours")
        again = pending_dialog(manager.state.entity_states)
        await _answer(manager, "Bye")

        # Assert
        assert first["messages"][0] == 'Goran: "What do you want?"'
        assert again["node"] == "root"
        assert [o["label"] for o in again["options"]] == ["Gear for the wild.", "Bye."]
        assert pending_dialog(manager.state.entity_states) is None
        assert _vars(manager)["asked_mine"] is True
        assert _vars(manager)["goran_path"] == ["root:1", "root:2"]
        rows = (await db.execute(select(ChatMessage.content))).scalars().all()
        assert "[Choice] Rumours about the mine?" in rows


@pytest.mark.asyncio
async def test_condition_hides_response():
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _manager(db, gold=0)

        # Act
        await _answer(manager, "Gear")

        # Assert
        options = pending_dialog(manager.state.entity_states)["options"]
        assert [o["label"] for o in options] == ["Too expensive."]


@pytest.mark.asyncio
async def test_action_reaches_handler_and_stays_on_node():
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _manager(db, gold=300)
        await _answer(manager, "Gear")

        # Act
        await _answer(manager, "I take the sword")

        # Assert
        assert _vars(manager)["last_action"] == "BUY_SWORD"
        assert pending_dialog(manager.state.entity_states)["node"] == "equipment"


def test_validator_sees_tree_handlers():
    # Act
    handlers = dialog_handlers(OPEN_TREE)

    # Assert
    assert handlers == {"on_goran_end", "on_goran_action"}
