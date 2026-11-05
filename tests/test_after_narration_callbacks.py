"""Direction callbacks: tw.story.direct / tw.npcs.say_directed(..., after=...) run after the narration."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from backend.api.routes.adventures import dialog_service
from backend.api.routes.adventures.after_narration import run_after_narration
from backend.api.routes.adventures.dialog_service import DialogChoiceResolver
from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.engine.rules.rule_engine import GameEvent
from backend.engine.scripting.context import GameContext
from backend.engine.scripting.dialog import pending_dialog
from backend.engine.scripting.gm_directions import (
    AFTER_NARRATION_KEY,
    pending_after_narration,
    pending_gm_directions,
)
from backend.engine.scripting.npc_directions import NPCDirectionMixin
from backend.engine.scripting.runner import ScriptRunner
from backend.models.chat import ChatMessage
from tests.conftest import TestSessionLocal
from tests.test_game_loop import _seed_game_context

INIT_SCRIPT = """
def give_back(npc_name, item_name):
    tw.story.system(npc_name + ' gives ' + item_name + ' back to you.')
    tw.vars.set('given_back', item_name)

def on_offer(answ):
    tw.npcs.say_directed('BRAM', 'grumbles about the deal', after='give_back',
                         after_args={'npc_name': 'Bram', 'item_name': 'Teacup'})
"""
QUEUE_GIVE_BACK = (
    "tw.story.direct('Bram grumbles', after='give_back', "
    "after_args={'npc_name': 'Bram', 'item_name': 'Teacup'})"
)


def _run(code: str, context: GameContext) -> None:
    ScriptRunner([], init_script=INIT_SCRIPT).execute_code(code, {"tw": context, "game": context})


async def _manager(db) -> GameTurnManager:
    user, adv, _avatar, _state = await _seed_game_context(db)
    adv.original_manifest = {"init_script": INIT_SCRIPT}
    await db.commit()
    manager = GameTurnManager(db, "session-1", user)
    await manager.initialize()
    return manager


def test_direct_with_after_queues_callback_next_to_direction():
    context = GameContext()

    _run(QUEUE_GIVE_BACK, context)

    assert context.changeset.gm_directions == ["Bram grumbles"]
    assert context.changeset.after_narration == [
        {"handler": "give_back", "args": {"npc_name": "Bram", "item_name": "Teacup"}}
    ]


def test_say_directed_accepts_a_function_as_after():
    class Npc(NPCDirectionMixin):
        id = "BRAM"
        name = "Bram"

    context = GameContext()
    npc = Npc()
    npc._changeset = context.changeset

    def give_back():
        pass

    npc.say_directed("hands it back", after=give_back)

    assert len(context.changeset.gm_directions) == 1
    assert context.changeset.after_narration == [{"handler": "give_back", "args": {}}]


@pytest.mark.parametrize(
    "after,after_args",
    [
        ("not a name!", None),
        ("give_back", "item"),
        ("give_back", {"item": object()}),
        ("give_back", {"bad-key": 1}),
    ],
)
def test_unusable_callback_is_reported_and_direction_kept(after, after_args):
    context = GameContext()

    context.story.direct("Bram grumbles", after=after, after_args=after_args)

    assert context.changeset.gm_directions == ["Bram grumbles"]
    assert context.changeset.after_narration == []
    assert context.changeset.system_messages[0].startswith("Script error: direction callback")


@pytest.mark.asyncio
async def test_callback_waits_in_session_and_runs_once(setup_test_db):
    async with TestSessionLocal() as db:
        manager = await _manager(db)
        await manager._execute_inline_script(QUEUE_GIVE_BACK, "on_receive_item", "BRAM")

        assert pending_after_narration(manager.state.entity_states)

        messages, ended = await run_after_narration(manager)
        again, _ = await run_after_narration(manager)

    assert [str(m) for m in messages] == ["Bram gives Teacup back to you."]
    assert ended is False
    assert again == []
    assert AFTER_NARRATION_KEY not in manager.state.entity_states
    assert manager.state.entity_states["__script_vars__"]["given_back"] == "Teacup"


@pytest.mark.asyncio
async def test_missing_handler_is_reported_visibly(setup_test_db):
    async with TestSessionLocal() as db:
        manager = await _manager(db)
        await manager._execute_inline_script(
            "tw.story.direct('x', after='nowhere')", "on_receive_item", "BRAM"
        )

        messages, _ = await run_after_narration(manager)

    assert "the callback 'nowhere' is not defined" in str(messages[0])


@pytest.mark.asyncio
async def test_turn_narration_comes_before_the_callback(setup_test_db, monkeypatch):
    llm = MagicMock()
    llm.aexecute_complex_task = AsyncMock(return_value=GameEvent(narrative_description="Bram."))

    async def stream(*_args, **_kwargs):
        yield MagicMock(choices=[MagicMock(delta=MagicMock(content="Bram grumbles at you."))])

    llm.stream_simple_task = AsyncMock(side_effect=stream)
    monkeypatch.setattr(
        "backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *a, **k: llm
    )

    async with TestSessionLocal() as db:
        manager = await _manager(db)
        await manager._execute_inline_script(QUEUE_GIVE_BACK, "on_receive_item", "BRAM")
        await db.commit()

        events = [event async for event in manager.process_turn("look at Bram")]
        rows = (
            (
                await db.execute(
                    select(ChatMessage)
                    .where(ChatMessage.session_id == "session-1")
                    .order_by(ChatMessage.created_at, ChatMessage.id)
                )
            )
            .scalars()
            .all()
        )

    contents = [row.content for row in rows]
    narration_at = contents.index("Bram grumbles at you.")
    callback_at = contents.index("Bram gives Teacup back to you.")
    assert narration_at < callback_at
    streamed = "".join(events)
    assert streamed.index("Bram grumbles at you.") < streamed.index("Bram gives Teacup back")
    assert pending_gm_directions(manager.state.entity_states) == []


@pytest.mark.asyncio
async def test_dialog_narration_runs_callbacks_queued_by_the_handler(setup_test_db, monkeypatch):
    class FakeLLM:
        def __init__(self, *_args, **_kwargs):
            pass

        async def aexecute_simple_task(self, *_args, **_kwargs):
            return "Bram grumbles about the deal."

    monkeypatch.setattr(dialog_service, "GameMasterLLM", FakeLLM)
    async with TestSessionLocal() as db:
        manager = await _manager(db)
        await manager._execute_inline_script(
            "tw.dialog.choose('Deal?', ['Yes', 'No'], on_choice='on_offer', narrate=True)",
            "on_interact",
            "BRAM",
        )
        await db.commit()
        dialog_id = pending_dialog(manager.state.entity_states)["id"]

        result = await DialogChoiceResolver(manager).resolve(dialog_id, 0, None)

    assert result["messages"][-2:] == [
        "Bram grumbles about the deal.",
        "Bram gives Teacup back to you.",
    ]


def test_validator_flags_callback_missing_from_init_script():
    from backend.core.dialog_validator import check_dialog_handlers

    sources = [
        {
            "script": (
                "tw.npcs.say_directed('BRAM', 'grumbles', after='give_back')\n"
                "tw.story.direct('x', after='typo_handler')"
            )
        }
    ]

    findings = check_dialog_handlers(sources, INIT_SCRIPT)

    assert [(f.code, f.context["handler"]) for f in findings] == [
        ("direction_callback_missing", "typo_handler")
    ]
