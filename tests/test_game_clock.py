"""In-game clock: narration ticks, GM time control, tw.time API, time events and debug commands."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from backend.api.routes.adventures.game_clock_flow import tick_after_narration
from backend.engine.blueprint import analyze_blueprint
from backend.engine.debug_commands.debug_engine import DebugEngine
from backend.engine.debug_commands.time_commands import TIME_CHANGED_MARKER
from backend.engine.rules.game_clock import (
    CLOCK_STATE_KEY,
    apply_changeset_clock,
    apply_clock_ops,
    apply_gm_time_request,
    clock_view,
    collect_due_events,
    narration_tick,
    read_clock,
    to_minutes,
)
from backend.engine.rules.rule_engine import GameEvent
from backend.engine.scripting.context import GameContext
from backend.engine.scripting.runner import ScriptRunner
from backend.models.session_state import SessionState


def _adventure(**overrides):
    values = {"time_per_turn": 5, "gm_time_control": True, "max_time_per_turn": None}
    values.update(overrides)
    return SimpleNamespace(time_config=None, time_system="calendar", **values)


def _state(minutes: int = 0, clock: dict | None = None) -> SimpleNamespace:
    states = {CLOCK_STATE_KEY: clock} if clock is not None else {}
    return SimpleNamespace(
        in_game_time=minutes,
        entity_states=states,
        start_datetime=None,
        time_system="calendar",
        time_config=None,
    )


# --- Parsing and operations ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(90, 90), ("90", 90), ("2h 30m", 150), ("1d", 1440), ("1w 1d", 11520), ("1:30", 90)],
)
def test_to_minutes_parses_amounts(raw, expected) -> None:
    # Act / Assert
    assert to_minutes(raw) == expected


@pytest.mark.parametrize("raw", ["", "soon", "2 hours", True, None])
def test_to_minutes_rejects_non_amounts(raw) -> None:
    # Act / Assert
    assert to_minutes(raw) is None


def test_apply_clock_ops_replays_in_order_and_clamps() -> None:
    # Arrange
    ops = [
        {"op": "advance", "minutes": 30},
        {"op": "advance", "minutes": -100},
        {"op": "set", "minutes": 60},
        {"op": "pause", "paused": True},
        {"op": "tick_minutes", "minutes": 15},
        {"op": "gm_control", "allowed": False},
    ]

    # Act
    minutes, clock = apply_clock_ops(10, read_clock({}), ops)

    # Assert
    assert minutes == 60
    assert clock["paused"] is True
    assert clock["minutes_per_tick"] == 15
    assert clock["gm_time_control"] is False


# --- Narration ticks and GM control --------------------------------------------------------


def test_narration_tick_uses_override_and_respects_pause() -> None:
    # Arrange
    clock = read_clock({})
    clock["minutes_per_tick"] = 12

    # Act
    after_tick, elapsed = narration_tick(0, clock, _adventure())
    clock["paused"] = True
    after_pause, paused_elapsed = narration_tick(after_tick, clock, _adventure())

    # Assert
    assert (after_tick, elapsed) == (12, 12)
    assert (after_pause, paused_elapsed) == (12, 0)
    assert clock["ticks"] == 1


def test_gm_time_request_applies_capped_extra_time() -> None:
    # Arrange
    state = _state(minutes=100)
    event = GameEvent(extra_time_minutes=40)

    # Act
    changed = apply_gm_time_request(state, _adventure(max_time_per_turn=20), event)

    # Assert: tick (5) + extra is capped at 20 -> 15 extra minutes
    assert changed is True
    assert state.in_game_time == 115


@pytest.mark.parametrize(
    ("adventure", "clock"),
    [
        (_adventure(gm_time_control=False), None),
        (_adventure(), {"paused": True}),
        (_adventure(), {"gm_time_control": False}),
    ],
)
def test_gm_time_request_is_ignored_without_gm_time_control(adventure, clock) -> None:
    # Arrange
    state = _state(minutes=100, clock=clock)
    event = GameEvent(extra_time_minutes=20, time_override_minutes=999)

    # Act
    changed = apply_gm_time_request(state, adventure, event)

    # Assert
    assert changed is False
    assert state.in_game_time == 100


# --- tw.time --------------------------------------------------------------------------------


def _context(state: SimpleNamespace, adventure=None) -> GameContext:
    return GameContext(
        in_game_time=state.in_game_time,
        clock=clock_view(state, adventure or _adventure()),
        is_debug_enabled=True,
    )


def test_tw_time_reads_its_own_changes_and_records_ops() -> None:
    # Arrange
    state = _state(minutes=30)
    ctx = _context(state)
    code = (
        "tw.time.advance('1h')\n"
        "tw.vars.set('now', tw.time.now)\n"
        "tw.vars.set('game_time', tw.game.time)\n"
        "tw.time.set_minutes_per_tick(10)\n"
        "tw.time.pause()\n"
        "tw.vars.set('paused', tw.time.is_paused)\n"
        "tw.vars.set('gm', tw.time.gm_can_change_time)\n"
    )

    # Act
    ScriptRunner([]).execute_code(code, {"tw": ctx})
    entity_states: dict = {}
    apply_changeset_clock(state, entity_states, ctx.changeset.clock_ops)

    # Assert
    assert ctx.changeset.var_updates["now"] == 90
    assert ctx.changeset.var_updates["game_time"] == 90
    assert ctx.changeset.var_updates["paused"] is True
    assert ctx.changeset.var_updates["gm"] is False
    assert state.in_game_time == 90
    assert entity_states[CLOCK_STATE_KEY]["minutes_per_tick"] == 10
    assert entity_states[CLOCK_STATE_KEY]["paused"] is True


def test_tw_time_clock_of_day_uses_start_time() -> None:
    # Arrange
    state = _state(minutes=24 * 60 + 90)
    state.time_config = {"start_time": "08:00", "initial_day": 1}
    ctx = _context(state)

    # Act / Assert
    assert (ctx.time.day, ctx.time.hour, ctx.time.minute) == (2, 9, 30)
    assert ctx.time.format() == "Day 2, 09:30"


def test_tw_time_timers_need_a_function_handler() -> None:
    # Arrange
    ctx = _context(_state(minutes=0))
    code = (
        "def on_alarm(event):\n"
        "    tw.narrate('Alarm!')\n"
        "tw.vars.set('ok', tw.time.after('30m', on_alarm, timer_id='ALARM', data={'n': 1}))\n"
        "tw.vars.set('bad', tw.time.at(10, 'not a name!'))\n"
    )

    # Act
    ScriptRunner([]).execute_code(code, {"tw": ctx})

    # Assert
    assert ctx.changeset.var_updates["ok"] == "ALARM"
    assert ctx.changeset.var_updates["bad"] is None
    assert ctx.time.timers == [
        {"id": "ALARM", "at": 30, "handler": "on_alarm", "every": None, "data": {"n": 1}}
    ]


# --- Time events ----------------------------------------------------------------------------


def test_time_scripts_fire_once_and_rearm_when_time_goes_back() -> None:
    # Arrange
    scripts = [{"id": "DUSK", "trigger": "on_time_reached", "target_id": "2h", "code": "pass"}]
    clock = read_clock({})

    # Act
    first = collect_due_events(130, clock, scripts)
    again = collect_due_events(200, clock, scripts)
    collect_due_events(60, clock, scripts)  # rewound below the threshold
    rearmed = collect_due_events(120, clock, scripts)

    # Assert
    assert [e["id"] for e in first] == ["DUSK"]
    assert again == []
    assert [e["id"] for e in rearmed] == ["DUSK"]


def test_one_shot_timers_are_removed_and_repeating_timers_move_on() -> None:
    # Arrange
    clock = read_clock({})
    clock["timers"] = [
        {"id": "ONCE", "at": 10, "handler": "h", "every": None, "data": None},
        {"id": "LOOP", "at": 10, "handler": "h", "every": 15, "data": None},
        {"id": "LATER", "at": 500, "handler": "h", "every": None, "data": None},
    ]

    # Act
    due = collect_due_events(32, clock, [])

    # Assert
    assert {e["id"] for e in due} == {"ONCE", "LOOP"}
    assert {t["id"]: t["at"] for t in clock["timers"]} == {"LOOP": 40, "LATER": 500}


@pytest.mark.asyncio
async def test_tick_after_narration_advances_clock_and_runs_due_timer_handler() -> None:
    # Arrange
    clock = read_clock({})
    clock["timers"] = [{"id": "BOMB", "at": 5, "handler": "explode", "every": None, "data": 3}]
    state = SessionState(
        in_game_time=0, entity_states={CLOCK_STATE_KEY: clock}, time_system="calendar"
    )
    adventure = _adventure()
    runner = ScriptRunner(
        [], init_script="def explode(event):\n    tw.narrate('Boom ' + str(event['data']))\n"
    )
    applied: list = []

    async def apply_changeset(changeset, *_args):
        applied.append(changeset)
        return list(changeset.narrative_messages)

    manager = SimpleNamespace(
        state=state,
        adventure=adventure,
        clock_tick_pending=True,
        _get_script_runner=lambda: runner,
        _build_script_context=AsyncMock(side_effect=lambda: _context(state, adventure)),
        _apply_script_changeset=apply_changeset,
        _save_chat_message=AsyncMock(),
        _finalize_session=AsyncMock(),
    )

    # Act
    events = [e async for e in tick_after_narration(manager)]
    second = [e async for e in tick_after_narration(manager)]

    # Assert
    assert state.in_game_time == 5
    assert any("Boom 3" in e for e in events)
    assert second == []  # only one tick per player message
    assert read_clock(state.entity_states)["timers"] == []
    assert len(applied) == 1


# --- Debug commands and blueprint -----------------------------------------------------------


@pytest.mark.asyncio
async def test_debug_time_commands_change_and_report_the_clock() -> None:
    # Arrange
    state = SessionState(in_game_time=0, entity_states={}, time_system="calendar")
    adventure = _adventure(original_manifest={})

    # Act
    set_reply = await DebugEngine.handle_debug_command(
        None, state, "time set 2h", adventure=adventure
    )
    await DebugEngine.handle_debug_command(None, state, "time pause", adventure=adventure)
    tick_reply = await DebugEngine.handle_debug_command(
        None, state, "time tick 3", adventure=adventure
    )
    status = await DebugEngine.handle_debug_command(None, state, "time", adventure=adventure)

    # Assert
    assert set_reply.startswith(TIME_CHANGED_MARKER)
    assert state.in_game_time == 120
    assert "paused" in tick_reply
    assert "Paused: True" in status
    assert "GM may change time: False" in status


def test_blueprint_script_at_key_stores_minutes() -> None:
    # Arrange
    text = (
        "[Script: SUNSET] Night falls\n"
        "trigger: on_time_reached\n"
        "at: 10h 30m\n"
        "code: tw.narrate('The sun sets.')\n"
    )

    # Act
    blueprint, missing_ids = analyze_blueprint(text)

    # Assert
    block = blueprint.first("script")
    assert not blueprint.errors
    assert missing_ids == []
    assert block.fixed()["target_id"] == "630"


# --- Full turn ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_turn_ticks_once_ignores_locked_gm_time_and_fires_time_script(
    setup_test_db, monkeypatch
):
    # Arrange
    from unittest.mock import MagicMock

    from backend.api.routes.adventures.gameplay_logic import GameTurnManager
    from backend.models.adventure_template import AdventureTemplate
    from backend.models.avatar import Avatar
    from backend.models.game_session import GameSession
    from backend.models.user import User
    from tests.conftest import TestSessionLocal

    script = {
        "id": "DUSK",
        "trigger": "on_time_reached",
        "target_id": "10",
        "code": "tw.narrate('Dusk falls over the valley.')",
    }
    async with TestSessionLocal() as db:
        user = User(username="clock_player", hashed_password="pw", role="user")
        adv = AdventureTemplate(
            id="adv-clock",
            title="Clock Test",
            owner_id="admin",
            time_per_turn=10,
            gm_time_control=False,
            strict_rules=True,
            original_manifest={"scripts": [script]},
        )
        db.add_all([user, adv])
        await db.flush()
        avatar = Avatar(id="av-clock", template_id=adv.id, user_id=user.id, name="Hero", hp=100)
        db.add(avatar)
        await db.flush()
        db.add_all(
            [
                GameSession(
                    id="session-clock",
                    template_id=adv.id,
                    user_id=user.id,
                    avatar_id=avatar.id,
                    adventure_title=adv.title,
                ),
                SessionState(
                    session_id="session-clock",
                    template_id=adv.id,
                    avatar_id=avatar.id,
                    user_id=user.id,
                    current_scene_id="START",
                    in_game_time=0,
                ),
            ]
        )
        await db.commit()

        llm = MagicMock()
        llm.aexecute_complex_task = AsyncMock(
            return_value=GameEvent(narrative_description="You search.", extra_time_minutes=60)
        )

        async def stream(*_args, **_kwargs):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="You search the hut."))])

        llm.stream_simple_task = AsyncMock(return_value=stream())
        monkeypatch.setattr(
            "backend.api.routes.adventures.gameplay_logic.GameMasterLLM",
            lambda *args, **kwargs: llm,
        )

        # Act
        manager = GameTurnManager(db, "session-clock", user)
        output = "".join([chunk async for chunk in manager.process_turn("I search the hut")])

        # Assert
        state = (
            await db.execute(select(SessionState).where(SessionState.session_id == "session-clock"))
        ).scalar_one()
        assert state.in_game_time == 10  # one tick, the GM's 60 extra minutes are ignored
        assert "Dusk falls over the valley." in output
        assert read_clock(state.entity_states)["fired_scripts"] == ["DUSK"]
        mechanics_call = llm.aexecute_complex_task.await_args_list[0]
        prompt_text = " ".join(str(a) for a in mechanics_call.args) + str(mechanics_call.kwargs)
        assert "TIME CONTROL: LOCKED" in prompt_text
