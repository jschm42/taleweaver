"""Sequence-scoped scripts and inline on_interact triggers on objects and NPCs."""

import pytest
from sqlalchemy import select

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.api.routes.adventures.interaction_hooks import fire_interact_triggers
from backend.engine.rules.sequence_scripts import sequence_scripts
from backend.models.chat import ChatMessage
from backend.models.world_entity import WorldEntity
from backend.schemas.adventure import AdventureTemplateUpdate
from tests.conftest import TestSessionLocal
from tests.test_game_loop import _seed_game_context

BOMB_SCRIPT = {
    "id": "SEQ_BOMB_TAMPER",
    "trigger": "on_interact",
    "target_id": "TICKING_BOMB",
    "code": "tw.vars.set('bomb_touched', tw.vars.get('bomb_touched', 0) + 1)",
}
SEQUENCES = [
    {"id": "SEQ_1_BOMB", "order": 1, "title": "Bomb", "scripts": [BOMB_SCRIPT]},
    {"id": "SEQ_2_AFTER", "order": 2, "title": "After", "scripts": []},
]


async def _manager(db, active_sequence_id: str, metadata: dict | None = None) -> GameTurnManager:
    user, adv, _avatar, state = await _seed_game_context(db)
    adv.sequences = SEQUENCES
    state.active_sequence_id = active_sequence_id
    db.add(
        WorldEntity(id="TICKING_BOMB", session_id=state.session_id, entity_type="OBJECT",
                    name="Ticking Bomb", description="A bomb.", current_scene_id="START",
                    item_type="STATIC", is_portable=False, metadata_json=metadata or {})
    )  # fmt: skip
    await db.commit()
    manager = GameTurnManager(db, state.session_id, user)
    await manager.initialize()
    return manager


def _touched(manager: GameTurnManager):
    return (manager.state.entity_states or {}).get("__script_vars__", {}).get("bomb_touched")


def test_sequence_scripts_skip_on_init_and_tag_sequence():
    # Arrange
    sequence = {
        "id": "SEQ_1",
        "scripts": [BOMB_SCRIPT, {"id": "X", "trigger": "on_init", "code": "pass"}, "junk"],
    }

    # Act
    scripts = sequence_scripts(sequence)

    # Assert
    assert [s["id"] for s in scripts] == ["SEQ_BOMB_TAMPER"]
    assert scripts[0]["sequence_id"] == "SEQ_1"
    assert sequence_scripts(None) == []


@pytest.mark.asyncio
async def test_sequence_script_runs_while_its_sequence_is_active():
    async with TestSessionLocal() as db:
        # Arrange
        active = await _manager(db, "SEQ_1_BOMB")

        # Act
        await fire_interact_triggers(active, active._get_script_runner(), "TICKING_BOMB", None)

        # Assert
        assert _touched(active) == 1


@pytest.mark.asyncio
async def test_sequence_script_is_ignored_in_other_sequences():
    async with TestSessionLocal() as db:
        # Arrange
        inactive = await _manager(db, "SEQ_2_AFTER")

        # Act
        await fire_interact_triggers(inactive, inactive._get_script_runner(), "TICKING_BOMB", None)

        # Assert
        assert _touched(inactive) is None


@pytest.mark.asyncio
async def test_inline_on_interact_trigger_runs_script_and_shows_text():
    async with TestSessionLocal() as db:
        # Arrange
        metadata = {
            "on_interact_script": "tw.vars.set('inline_fired', True)",
            "on_interact_text": "The timer flickers.",
        }
        manager = await _manager(db, "SEQ_2_AFTER", metadata)

        # Act
        messages, rejected = await fire_interact_triggers(
            manager, manager._get_script_runner(), "TICKING_BOMB", None
        )

        # Assert
        assert manager.state.entity_states["__script_vars__"]["inline_fired"] is True
        assert "The timer flickers." in [str(m) for m in messages]
        assert rejected == []
        rows = (await db.execute(select(ChatMessage.content))).scalars().all()
        assert "The timer flickers." in rows


def test_editor_update_model_keeps_sequence_scripts():
    # Act
    update = AdventureTemplateUpdate(sequences=SEQUENCES)

    # Assert
    dumped = update.model_dump()["sequences"][0]["scripts"][0]
    assert dumped["trigger"] == "on_interact"
    assert dumped["target_id"] == "TICKING_BOMB"


@pytest.mark.asyncio
async def test_chat_mode_inspect_command_fires_sequence_on_interact(monkeypatch):
    """Regression: without the mechanics pass (chat mode) on_interact never ran."""
    from unittest.mock import AsyncMock, MagicMock

    from backend.engine.rules.rule_engine import AdventureGeneratorToolIntent
    from backend.engine.scripting.dialog import pending_dialog

    async with TestSessionLocal() as db:
        # Arrange
        dialog_script = {
            **BOMB_SCRIPT,
            "code": "tw.dialog.choose('Which wire?', ['Red', 'Blue'], on_choice='on_wire')",
        }
        user, adv, _avatar, state = await _seed_game_context(db)
        adv.strict_rules = False
        adv.is_adventure_generator = False
        adv.sequences = [{**SEQUENCES[0], "scripts": [dialog_script]}]
        state.active_sequence_id = "SEQ_1_BOMB"
        db.add(
            WorldEntity(id="TICKING_BOMB", session_id=state.session_id, entity_type="OBJECT",
                        name="Bomb", description="A bomb.", current_scene_id="START",
                        item_type="STATIC", is_portable=False)
        )  # fmt: skip
        await db.commit()

        llm = MagicMock()
        llm.aexecute_complex_task = AsyncMock(return_value=AdventureGeneratorToolIntent())

        async def narration(*_args, **_kwargs):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="You study the bomb."))])

        llm.stream_simple_task = AsyncMock(return_value=narration())
        monkeypatch.setattr(
            "backend.api.routes.adventures.gameplay_logic.GameMasterLLM",
            lambda *args, **kwargs: llm,
        )
        manager = GameTurnManager(db, state.session_id, user)

        # Act
        async for _ in manager.process_turn("/inspect Bomb"):
            pass

        # Assert
        await db.refresh(state)
        dialog = pending_dialog(state.entity_states)
        assert dialog is not None
        assert dialog["prompt"] == "Which wire?"
