"""Script-driven choice dialogs: tw.dialog.choose opens, the choice endpoint runs the handler."""

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from backend.api.routes.adventures import agent_dialog, dialog_service
from backend.api.routes.adventures.agent_turn_stream import _agent_dialog_events
from backend.api.routes.adventures.dialog_service import DialogChoiceResolver
from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.core.script_validator import check_scripts_and_guards
from backend.engine.scripting.context import GameContext
from backend.engine.scripting.dialog import client_dialog, pending_dialog
from backend.engine.scripting.runner import ScriptRunner
from backend.models.chat import ChatMessage
from tests.conftest import TestSessionLocal
from tests.test_game_loop import _seed_game_context

INIT_SCRIPT = """
def on_bomb_wire(answ):
    if answ == 0:
        tw.vars.set('bomb_disarmed', 1)
        tw.narrate('You disarmed the trap.')
        return
    if answ == 1:
        tw.game.game_over('The bomb exploded.')
        return
    tw.dialog.choose('It keeps ticking. Now what?', ['Run', 'Pray'], on_choice=on_bomb_wire)
"""
OPEN_BOMB_DIALOG = (
    "tw.dialog.choose('The bomb starts ticking.', "
    "['Cut the red wire', 'Cut the blue wire', 'Scream like a baby'], on_choice='on_bomb_wire')"
)


def _run(code: str, context: GameContext, init_script: str = INIT_SCRIPT) -> None:
    runner = ScriptRunner([], init_script=init_script)
    runner.execute_code(code, {"tw": context, "game": context})


async def _manager(db, narrate: bool = False) -> GameTurnManager:
    user, adv, _avatar, _state = await _seed_game_context(db)
    adv.original_manifest = {"init_script": INIT_SCRIPT}
    await db.commit()
    manager = GameTurnManager(db, "session-1", user)
    await manager.initialize()
    code = OPEN_BOMB_DIALOG.replace(")", f", narrate={narrate})") if narrate else OPEN_BOMB_DIALOG
    await manager._execute_inline_script(code, "on_pickup", "BOMB")
    await db.commit()
    return manager


def _dialog(manager: GameTurnManager) -> dict:
    return pending_dialog(manager.state.entity_states)


def test_choose_records_pending_dialog_with_author_indices():
    # Arrange
    context = GameContext()

    # Act
    _run(OPEN_BOMB_DIALOG, context)

    # Assert
    dialog = context.changeset.pending_dialog
    assert dialog["handler"] == "on_bomb_wire"
    assert [o["index"] for o in dialog["options"]] == [0, 1, 2]
    assert context.changeset.has_changes


def test_visible_if_hides_options_but_keeps_original_index():
    # Arrange
    context = GameContext(script_vars={"has_pliers": False})
    code = (
        "tw.dialog.choose('Wires?', [{'label': 'Use pliers', "
        "'visible_if': \"tw.vars.get('has_pliers') == True\"}, 'Pull'], on_choice='on_bomb_wire')"
    )

    # Act
    _run(code, context)

    # Assert
    assert context.changeset.pending_dialog["options"] == [{"index": 1, "label": "Pull"}]


def test_function_reference_is_accepted_and_second_dialog_ignored():
    # Arrange
    context = GameContext()
    code = (
        "tw.dialog.choose('A?', ['x'], on_choice=on_bomb_wire)\n"
        "opened = tw.dialog.choose('B?', ['y'], on_choice=on_bomb_wire)\n"
        "tw.vars.set('second_opened', opened)"
    )

    # Act
    _run(code, context)

    # Assert
    assert context.changeset.pending_dialog["prompt"] == "A?"
    assert context.changeset.pending_dialog["handler"] == "on_bomb_wire"
    assert context.changeset.var_updates["second_opened"] is False


def test_invalid_handler_does_not_open_dialog():
    # Arrange
    context = GameContext()

    # Act
    _run("tw.dialog.choose('A?', ['x'], on_choice='not valid()')", context)

    # Assert
    assert context.changeset.pending_dialog is None


def test_client_dialog_hides_handler():
    # Arrange
    context = GameContext()
    _run(OPEN_BOMB_DIALOG, context)

    # Act
    payload = client_dialog(context.changeset.pending_dialog)

    # Assert
    assert "handler" not in payload
    assert payload["options"][2] == {"index": 2, "label": "Scream like a baby"}


@pytest.mark.asyncio
async def test_choice_runs_handler_and_clears_dialog():
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _manager(db)
        dialog_id = _dialog(manager)["id"]

        # Act
        result = await DialogChoiceResolver(manager).resolve(dialog_id, 0, None)

        # Assert
        assert result["messages"] == ["You disarmed the trap."]
        assert _dialog(manager) is None
        assert manager.state.entity_states["__script_vars__"]["bomb_disarmed"] == 1
        rows = (await db.execute(select(ChatMessage.content))).scalars().all()
        assert "[Choice] Cut the red wire" in rows


@pytest.mark.asyncio
async def test_handler_can_open_follow_up_dialog():
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _manager(db)
        first_id = _dialog(manager)["id"]

        # Act
        await DialogChoiceResolver(manager).resolve(first_id, 2, None)

        # Assert
        follow_up = _dialog(manager)
        assert follow_up["id"] != first_id
        assert follow_up["prompt"] == "It keeps ticking. Now what?"


@pytest.mark.asyncio
async def test_game_over_handler_ends_session():
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _manager(db)

        # Act
        await DialogChoiceResolver(manager).resolve(_dialog(manager)["id"], 1, None)

        # Assert
        assert manager.state.session.status == "game_over"


@pytest.mark.asyncio
async def test_missing_handler_reports_visible_error_without_debug_mode():
    async with TestSessionLocal() as db:
        # Arrange: the dialog is open, but the init_script with its handler got lost.
        manager = await _manager(db)
        manager.adventure.original_manifest = {}

        # Act
        result = await DialogChoiceResolver(manager).resolve(_dialog(manager)["id"], 0, None)

        # Assert
        assert len(result["messages"]) == 1
        assert result["messages"][0].startswith("Script error")
        assert "on_bomb_wire" in result["messages"][0]
        rows = (
            (await db.execute(select(ChatMessage.content).where(ChatMessage.role == "system")))
            .scalars()
            .all()
        )
        assert result["messages"][0] in rows


def test_failing_trigger_script_reports_visible_error():
    # Arrange
    context = GameContext()
    script = {"id": "SCRIPT_BROKEN", "trigger": "on_turn_end", "code": "undefined_name + 1"}
    runner = ScriptRunner([script])

    # Act
    runner.run_trigger("on_turn_end", context)

    # Assert
    errors = context.changeset.system_messages
    assert len(errors) == 1
    assert errors[0].startswith("Script error in 'SCRIPT_BROKEN'")


@pytest.mark.asyncio
async def test_stale_dialog_id_and_unknown_index_are_rejected():
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _manager(db)
        resolver = DialogChoiceResolver(manager)

        # Act
        with pytest.raises(HTTPException) as stale:
            await resolver.resolve("stale", 0, None)
        with pytest.raises(HTTPException) as unknown:
            await resolver.resolve(_dialog(manager)["id"], 7, None)

        # Assert
        assert stale.value.status_code == 409
        assert unknown.value.status_code == 400
        assert _dialog(manager) is not None


@pytest.mark.asyncio
async def test_narrated_choice_saves_llm_outcome(monkeypatch):
    class FakeLLM:
        def __init__(self, *_args, **_kwargs):
            pass

        async def aexecute_simple_task(self, _system, user_prompt, _model, **_kwargs):
            assert "Cut the red wire" in user_prompt
            return "The red wire parts with a soft snip."

    async with TestSessionLocal() as db:
        # Arrange
        monkeypatch.setattr(dialog_service, "GameMasterLLM", FakeLLM)
        manager = await _manager(db, narrate=True)

        # Act
        result = await DialogChoiceResolver(manager).resolve(_dialog(manager)["id"], 0, None)

        # Assert
        assert result["messages"][-1] == "The red wire parts with a soft snip."


def test_validator_flags_handler_missing_from_init_script():
    # Arrange
    payload = {
        "adventure": {"init_script": INIT_SCRIPT},
        "objects": [
            {"id": "BOMB", "item_type": "MISC", "on_pickup_script": OPEN_BOMB_DIALOG},
            {"id": "BOX", "on_read_script": "tw.dialog.ask('?', ['a'], on_choice='nowhere')"},
        ],
    }

    # Act
    findings = check_scripts_and_guards(payload)

    # Assert
    missing = [f for f in findings if f.code == "dialog_handler_missing"]
    assert [f.context["handler"] for f in missing] == ["nowhere"]


def _fake_agent_llm(option_number: int):
    class FakeAgentLLM:
        def __init__(self, *_args, **_kwargs):
            pass

        async def aexecute_complex_task(self, *, user_prompt, response_model, **_kwargs):
            assert "3. Scream like a baby" in user_prompt
            return response_model(thoughts="Red feels right.", option_number=option_number)

    return FakeAgentLLM


@pytest.mark.asyncio
async def test_agent_picks_option_chosen_by_model(monkeypatch):
    async with TestSessionLocal() as db:
        # Arrange
        monkeypatch.setattr(agent_dialog, "GameMasterLLM", _fake_agent_llm(1))
        manager = await _manager(db)

        # Act
        thoughts, option = await agent_dialog.decide_dialog_option(manager, _dialog(manager))

        # Assert
        assert thoughts == "Red feels right."
        assert option == {"index": 0, "label": "Cut the red wire"}


@pytest.mark.asyncio
async def test_agent_falls_back_to_first_option_on_invalid_answer(monkeypatch):
    async with TestSessionLocal() as db:
        # Arrange
        monkeypatch.setattr(agent_dialog, "GameMasterLLM", _fake_agent_llm(9))
        manager = await _manager(db)

        # Act
        _thoughts, option = await agent_dialog.decide_dialog_option(manager, _dialog(manager))

        # Assert
        assert option["index"] == 0


@pytest.mark.asyncio
async def test_agent_turn_answers_open_dialog_instead_of_playing(monkeypatch):
    async with TestSessionLocal() as db:
        # Arrange
        monkeypatch.setattr(agent_dialog, "GameMasterLLM", _fake_agent_llm(1))
        manager = await _manager(db)

        # Act
        events = [e async for e in _agent_dialog_events(db, manager, _dialog(manager))]

        # Assert
        assert any("[Choice] Cut the red wire" in e for e in events)
        assert any(e.startswith("event: final") for e in events)
        assert _dialog(manager) is None
        assert manager.state.entity_states["__script_vars__"]["bomb_disarmed"] == 1


@pytest.mark.asyncio
async def test_win_guard_after_choice_completes_adventure():
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _manager(db)
        manager.adventure.completed_guard_expression = "tw.vars.get('bomb_disarmed') == 1"
        await db.commit()

        # Act
        await DialogChoiceResolver(manager).resolve(_dialog(manager)["id"], 0, None)

        # Assert
        assert manager.state.session.status == "completed"
        assert manager.state.is_completed is True


@pytest.mark.asyncio
async def test_game_over_choice_tells_the_outcome_in_the_story():
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _manager(db)

        # Act
        result = await DialogChoiceResolver(manager).resolve(_dialog(manager)["id"], 1, None)

        # Assert
        assert result["messages"][-1] == "The bomb exploded."
        rows = (await db.execute(select(ChatMessage.role, ChatMessage.content))).all()
        assert ("assistant", "The bomb exploded.") in [tuple(r) for r in rows]


@pytest.mark.asyncio
async def test_final_sequence_completes_once_and_ends_adventure():
    from backend.api.routes.adventures.chat_snapshot import apply_pending_sequence_progress

    async with TestSessionLocal() as db:
        # Arrange
        manager = await _manager(db)
        manager.adventure.sequences = [
            {"id": "SEQ_1", "order": 1, "title": "Sixty Seconds", "exp_reward": 100,
             "completion_guard_expression": "tw.vars.get('bomb_disarmed') == 1"}
        ]  # fmt: skip
        await DialogChoiceResolver(manager).resolve(_dialog(manager)["id"], 0, None)
        exp_after_choice = manager.avatar.exp

        # Act: snapshot reloads (the client polls GET /chat every few seconds)
        reloaded = [
            await apply_pending_sequence_progress(
                db, manager.state, manager.adventure, manager.avatar, manager.user
            )
            for _ in range(3)
        ]

        # Assert
        assert reloaded == [False, False, False]
        assert manager.avatar.exp == exp_after_choice
        assert manager.state.session.status == "completed"
        rows = (await db.execute(select(ChatMessage.content))).scalars().all()
        assert sum(1 for r in rows if r.startswith("Sequence completed")) == 1


@pytest.mark.asyncio
async def test_snapshot_completing_final_sequence_ends_adventure():
    from backend.api.routes.adventures.chat_snapshot import apply_pending_sequence_progress

    async with TestSessionLocal() as db:
        # Arrange: the guard already holds, e.g. set by a script in chat mode
        manager = await _manager(db)
        manager.adventure.sequences = [
            {"id": "SEQ_1", "order": 1, "title": "Sixty Seconds", "exp_reward": 100,
             "completion_guard_expression": "tw.vars.get('bomb_disarmed') == 1"}
        ]  # fmt: skip
        manager.state.entity_states = {
            **manager.state.entity_states,
            "__script_vars__": {"bomb_disarmed": 1},
        }
        await db.commit()
        args = (db, manager.state, manager.adventure, manager.avatar, manager.user)

        # Act
        first, second = (
            await apply_pending_sequence_progress(*args),
            await apply_pending_sequence_progress(*args),
        )

        # Assert
        assert (first, second) == (True, False)
        assert manager.state.session.status == "completed"
