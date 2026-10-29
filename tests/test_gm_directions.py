import json

import pytest

from backend.api.routes.adventures import dialog_service
from backend.api.routes.adventures.dialog_service import DialogChoiceResolver
from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.api.routes.adventures.turn_prompt_layout import build_narration_turn_block
from backend.engine.scripting.context import GameContext
from backend.engine.scripting.dialog import pending_dialog
from backend.engine.scripting.gm_directions import (
    GM_DIRECTIONS_KEY,
    MAX_DIRECTION_LENGTH,
    MAX_GM_DIRECTIONS,
    format_gm_directions,
    pending_gm_directions,
    store_gm_directions,
)
from backend.engine.scripting.runner import ScriptRunner
from backend.models.world_entity import WorldEntity
from tests.conftest import TestSessionLocal
from tests.test_game_loop import _seed_game_context

INIT_SCRIPT = """
def on_mood(answ):
    if answ == 0:
        tw.npcs.get('BRAM').character = 'Very angry'
        tw.story.direct('Let Bram sing a sailor song')
"""


def _run(ctx: GameContext, code: str) -> None:
    ScriptRunner([]).execute_code(code, {"tw": ctx}, script_id="test")


def test_direct_records_cleaned_directions_and_ignores_empty_text():
    # Arrange
    ctx = GameContext()

    # Act
    _run(ctx, "tw.story.direct('  Let Bram\\n sing  ')\ntw.direct('Rain starts')\ntw.direct('  ')")

    # Assert
    assert ctx.changeset.gm_directions == ["Let Bram sing", "Rain starts"]
    assert ctx.changeset.has_changes


def test_direct_caps_the_text_length():
    # Arrange
    ctx = GameContext()

    # Act
    _run(ctx, "tw.direct('x' * 2000)")

    # Assert
    assert len(ctx.changeset.gm_directions[0]) == MAX_DIRECTION_LENGTH


def test_store_keeps_only_the_newest_directions():
    # Arrange
    states: dict = {GM_DIRECTIONS_KEY: ["old"]}

    # Act
    store_gm_directions(states, [f"d{i}" for i in range(MAX_GM_DIRECTIONS)])

    # Assert
    assert pending_gm_directions(states) == [f"d{i}" for i in range(MAX_GM_DIRECTIONS)]


def test_narration_turn_block_contains_author_directions():
    # Arrange
    directions = format_gm_directions(["Let Bram sing a sailor song"])

    # Act
    block = build_narration_turn_block("STATE", "draft", "{}", [], author_directions=directions)

    # Assert
    assert "AUTHOR DIRECTIONS" in block
    assert "- Let Bram sing a sailor song" in block
    assert format_gm_directions([]) == ""


async def _manager(db) -> GameTurnManager:
    user, adv, _avatar, _state = await _seed_game_context(db)
    adv.original_manifest = {"init_script": INIT_SCRIPT}
    db.add(
        WorldEntity(
            id="BRAM",
            session_id="session-1",
            entity_type="NPC",
            name="Bram",
            description="A mechanic.",
            current_scene_id="START",
            character="Blunt",
        )
    )
    await db.commit()
    manager = GameTurnManager(db, "session-1", user)
    await manager.initialize()
    await manager._execute_inline_script(
        "tw.dialog.choose('Mood?', ['Angry', 'Calm'], on_choice='on_mood', narrate=True)",
        "on_interact",
        "BRAM",
    )
    await db.commit()
    return manager


@pytest.mark.asyncio
async def test_narrated_choice_gets_personas_and_consumes_directions(monkeypatch):
    seen: dict = {}

    class FakeLLM:
        def __init__(self, *_args, **_kwargs):
            pass

        async def aexecute_simple_task(self, _system, user_prompt, _model, **_kwargs):
            seen.update(json.loads(user_prompt))
            return "Bram bellows a sea shanty."

    async with TestSessionLocal() as db:
        # Arrange
        monkeypatch.setattr(dialog_service, "GameMasterLLM", FakeLLM)
        manager = await _manager(db)
        dialog_id = pending_dialog(manager.state.entity_states)["id"]

        # Act
        await DialogChoiceResolver(manager).resolve(dialog_id, 0, None)

        # Assert
        assert seen["author_directions"] == ["Let Bram sing a sailor song"]
        assert {"name": "Bram", "character": "Very angry", "goal": ""} in seen["npcs_present"]
        assert pending_gm_directions(manager.state.entity_states) == []


@pytest.mark.asyncio
async def test_directions_wait_for_the_next_turn_without_dialog_narration():
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _manager(db)
        dialog = pending_dialog(manager.state.entity_states)
        dialog["narrate"] = False

        # Act
        await DialogChoiceResolver(manager).resolve(dialog["id"], 0, None)

        # Assert
        assert pending_gm_directions(manager.state.entity_states) == ["Let Bram sing a sailor song"]
