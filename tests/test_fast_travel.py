"""Travel time on exits and fast travel points (docs/specs/world_sections.md, phase 2)."""

from types import SimpleNamespace

import pytest
from sqlalchemy import select

from backend.api.routes.adventures.fast_travel_plan import load_travel_plan
from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.api.routes.adventures.travel_flow import apply_exit_travel
from backend.core.world_validator import validate_adventure
from backend.engine.blueprint import analyze_blueprint
from backend.engine.blueprint.merge import apply_blueprint
from backend.engine.interaction.route_finder import cheapest_route
from backend.engine.rules.fast_travel import (
    TRAVEL_KEY,
    apply_travel_ops,
    block_reason,
    read_travel,
    unlock_on_visit,
)
from backend.engine.rules.game_clock import CLOCK_STATE_KEY
from backend.engine.rules.travel_time import advance_travel_time, format_duration, travel_note
from backend.engine.scripting import GameContext
from backend.models.adventure_template import AdventureTemplate
from backend.models.chat import ChatMessage
from backend.models.world_entity import WorldExit, WorldScene
from backend.models.world_map import WorldMap
from tests.conftest import TestSessionLocal
from tests.test_combat_encounters import SESSION_ID, _seed

# --- travel time -----------------------------------------------------------------------------


def test_format_duration_and_travel_note():
    # Act / Assert
    assert format_duration(45) == "45 min"
    assert format_duration(480) == "8 h"
    assert format_duration(1590) == "1 d 2 h 30 min"
    way = SimpleNamespace(travel_label="a windy cliff path")
    assert travel_note(way, 150) == "The journey (a windy cliff path) takes 2 h 30 min."


def test_travel_time_respects_a_paused_clock():
    # Arrange
    running = SimpleNamespace(in_game_time=100, entity_states={})
    paused = SimpleNamespace(in_game_time=100, entity_states={CLOCK_STATE_KEY: {"paused": True}})

    # Act
    added = advance_travel_time(running, 480)
    skipped = advance_travel_time(paused, 480)

    # Assert
    assert (added, running.in_game_time) == (480, 580)
    assert (skipped, paused.in_game_time) == (0, 100)


def test_exit_travel_replaces_the_narration_tick():
    # Arrange
    manager = SimpleNamespace(
        state=SimpleNamespace(in_game_time=0, entity_states={}),
        clock_tick_pending=True,
        travel_events_pending=False,
    )

    # Act
    notes = apply_exit_travel(manager, SimpleNamespace(travel_minutes=480, travel_label=None))
    none = apply_exit_travel(manager, SimpleNamespace(travel_minutes=None, travel_label=None))

    # Assert
    assert notes == ["The journey takes 8 h."] and none == []
    assert manager.state.in_game_time == 480
    assert manager.clock_tick_pending is False and manager.travel_events_pending is True


# --- fast travel record and scripts ----------------------------------------------------------


def test_travel_ops_unlock_lock_and_switch_off():
    # Arrange
    states = {TRAVEL_KEY: {"unlocked": ["TOWN"]}}
    ops = [
        {"op": "unlock", "scene_id": "cave"},
        {"op": "lock", "scene_id": "TOWN"},
        {"op": "enable", "enabled": False, "reason": "The roads are flooded."},
    ]

    # Act
    apply_travel_ops(states, ops)
    record = read_travel(states)

    # Assert
    assert record == {"unlocked": ["CAVE"], "disabled": True, "reason": "The roads are flooded."}
    assert block_reason(SimpleNamespace(fast_travel_enabled=True), None, record) == (
        "The roads are flooded."
    )


def test_block_reason_covers_adventure_and_chapter():
    # Arrange
    record = read_travel({})

    # Act / Assert
    assert "adventure" in block_reason(SimpleNamespace(fast_travel_enabled=False), None, record)
    assert "chapter" in block_reason(
        SimpleNamespace(fast_travel_enabled=True), {"fast_travel_allowed": False}, record
    )
    assert block_reason(SimpleNamespace(fast_travel_enabled=True), {}, record) == ""


def test_tw_game_fast_travel_calls_record_ops_and_read_them():
    # Arrange
    ctx = GameContext(travel={"unlocked": ["TOWN"]})

    # Act
    ctx.game.unlock_fast_travel("waystone")
    ctx.game.set_fast_travel(False, "A storm.")

    # Assert
    assert ctx.game.fast_travel_points == ["TOWN", "WAYSTONE"]
    assert ctx.game.fast_travel_enabled is False
    assert ctx.changeset.has_changes and len(ctx.changeset.travel_ops) == 2


def test_only_visit_points_unlock_on_entry():
    # Arrange
    states: dict = {}
    visit = SimpleNamespace(id="TOWN", is_fast_travel_point=True, fast_travel_unlock="visit")
    script = SimpleNamespace(id="CAVE", is_fast_travel_point=True, fast_travel_unlock="script")
    plain = SimpleNamespace(id="ROAD", is_fast_travel_point=False, fast_travel_unlock="visit")

    # Act
    results = [unlock_on_visit(states, scene) for scene in (visit, script, plain, visit)]

    # Assert
    assert results == [True, False, False, False]
    assert read_travel(states)["unlocked"] == ["TOWN"]


# --- route finder ----------------------------------------------------------------------------


def _step(source, target, minutes=0, solo=False, locked=False):
    return SimpleNamespace(
        source=source,
        target=target,
        travel_minutes=minutes,
        companions_allowed=not solo,
        locked=locked,
        exit_id=f"{source}-{target}",
    )


def test_cheapest_route_prefers_time_then_solo_avoidance():
    # Arrange: A -> C directly takes 10 h; A -> B -> C takes 2 h but B -> C is a solo passage.
    exits = {
        "A": [_step("A", "C", 600), _step("A", "B", 60)],
        "B": [_step("B", "C", 60, solo=True)],
    }

    # Act
    fastest = cheapest_route(exits, "A", "C", lambda _s: True)
    with_companion = cheapest_route(exits, "A", "C", lambda _s: True, avoid_solo=True)
    blocked = cheapest_route({"A": [_step("A", "C", locked=True)]}, "A", "C", lambda _s: True)

    # Assert
    assert [s.target for s in fastest] == ["B", "C"]
    assert [s.target for s in with_companion] == ["C"]
    assert blocked is None


# --- authoring -------------------------------------------------------------------------------


def test_blueprint_travel_keys_reach_the_manifest():
    # Arrange
    text = (
        "[World]\nfast_travel: no\n"
        "[Scene: SQUARE] Square\nfast_travel: yes\n"
        "[Scene: STONE] Waystone\nwaypoint: yes\nfast_travel_unlock: script\n"
        "[Exit: SQUARE -> STONE] the old road\ntravel: 2h 30m\ntravel_label: a long walk\n"
        "[Sequence: 1] Siege\nfast_travel: no\n"
    )
    manifest = {"scenes": [{"id": "SQUARE"}, {"id": "STONE"}], "sequences": [{"order": 1}]}

    # Act
    blueprint, _ = analyze_blueprint(text)
    apply_blueprint(manifest, blueprint)

    # Assert
    assert blueprint.issues == []
    assert manifest["fast_travel_enabled"] is False
    assert manifest["scenes"][1]["fast_travel_unlock"] == "script"
    assert manifest["exits"][0]["travel_minutes"] == 150
    assert manifest["sequences"][0]["fast_travel_allowed"] is False


def test_validator_flags_unreachable_script_points_and_untimed_region_exits():
    # Arrange
    payload = {
        "adventure": {
            "world_sections": [{"id": "A", "label": "A"}, {"id": "B", "label": "B"}],
            "scripts": [{"code": "tw.game.unlock_fast_travel('OK_POINT')"}],
        },
        "scenes": [
            {"id": "X", "section_id": "A", "is_fast_travel_point": True, "fast_travel_unlock": "script"},
            {"id": "OK_POINT", "section_id": "A", "is_fast_travel_point": True, "fast_travel_unlock": "script"},
            {"id": "Y", "section_id": "B"},
        ],
        "exits": [{"id": "e1", "from_scene_id": "X", "to_scene_id": "Y"}],
    }  # fmt: skip

    # Act
    findings = validate_adventure(payload)

    # Assert
    never = [f for f in findings if f.code == "fast_travel_point_never_unlocked"]
    assert [f.context["scene_id"] for f in never] == ["X"]
    codes = {f.code for f in findings}
    assert {"section_without_fast_travel_point", "region_exit_without_travel_time"} <= codes


# --- runtime ---------------------------------------------------------------------------------


async def _seed_world(db, *, unlocked=("TOWN",), states=None, enabled=True, road_text=None):
    user, avatar, state = await _seed(db)
    adv = await db.get(AdventureTemplate, "adv-enc")
    adv.fast_travel_enabled = enabled
    state.current_scene_id = "START"
    state.entity_states = {TRAVEL_KEY: {"unlocked": list(unlocked)}, **(states or {})}
    scenes = [
        WorldScene(id="START", label="Start", description="d", is_fast_travel_point=True),
        WorldScene(id="ROAD", label="Road", description="d", on_enter_scene_text=road_text),
        WorldScene(id="TOWN", label="Town", description="d", is_fast_travel_point=True),
    ]
    for scene in scenes:
        scene.session_id = SESSION_ID
    db.add_all(scenes)
    db.add_all(
        [
            WorldExit(id="x1", session_id=SESSION_ID, from_scene_id="START", to_scene_id="ROAD",
                      label="a gate", exit_type="bidirectional", travel_minutes=60),
            WorldExit(id="x2", session_id=SESSION_ID, from_scene_id="ROAD", to_scene_id="TOWN",
                      label="the high road", exit_type="bidirectional", travel_minutes=480),
        ]
    )  # fmt: skip
    nodes = {sid: {"id": sid, "label": sid.title()} for sid in ("START", "ROAD", "TOWN")}
    db.add(WorldMap(session_id=SESSION_ID, template_id="adv-enc", nodes=nodes, edges=[]))
    await db.commit()
    return user


async def _no_narration(*_args, **_kwargs):
    yield "event: done\ndata: {}\n\n"


async def _system_lines(db) -> list[str]:
    rows = await db.execute(
        select(ChatMessage.content).where(
            ChatMessage.session_id == SESSION_ID, ChatMessage.role == "system"
        )
    )
    return [row for row in rows.scalars().all()]


async def _travel(user, db, command):
    manager = GameTurnManager(db, SESSION_ID, user)
    await manager.initialize()
    chunks = [chunk async for chunk in manager.process_turn(command)]
    return manager, chunks


@pytest.mark.asyncio
async def test_fast_travel_walks_the_route_and_adds_the_travel_time(setup_test_db, monkeypatch):
    monkeypatch.setattr("backend.api.routes.adventures.fast_travel.narrate_arrival", _no_narration)
    async with TestSessionLocal() as db:
        # Arrange
        user = await _seed_world(db)

        # Act
        manager, _chunks = await _travel(user, db, "/fast_travel town")

        # Assert
        assert manager.state.current_scene_id == "TOWN"
        assert manager.state.in_game_time == 540
        lines = await _system_lines(db)
    assert "You travel from Start to Town (9 h)." in lines


@pytest.mark.asyncio
async def test_fast_travel_stops_when_something_happens_on_the_way(setup_test_db, monkeypatch):
    monkeypatch.setattr("backend.api.routes.adventures.fast_travel.narrate_arrival", _no_narration)
    async with TestSessionLocal() as db:
        # Arrange
        user = await _seed_world(db, road_text="A wolf blocks the road.")

        # Act
        manager, _chunks = await _travel(user, db, "/fast_travel Town")

        # Assert
        assert manager.state.current_scene_id == "ROAD"
        assert manager.state.in_game_time == 60
        lines = await _system_lines(db)
    assert any(line.startswith("You set out for Town but stop at Road") for line in lines)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kwargs", "command", "expected"),
    [
        ({"enabled": False}, "/fast_travel Town", "not available in this adventure"),
        (
            {"states": {"__pending_dialog__": {"options": ["a"]}}},
            "/fast_travel Town",
            "open choice",
        ),
        ({"unlocked": ()}, "/fast_travel Town", "no fast travel point called"),
        ({"unlocked": ("TOWN", "START")}, "/fast_travel Start", "You are here"),
    ],
)
async def test_fast_travel_refusals_leave_the_player_in_place(
    setup_test_db, monkeypatch, kwargs, command, expected
):
    monkeypatch.setattr("backend.api.routes.adventures.fast_travel.narrate_arrival", _no_narration)
    async with TestSessionLocal() as db:
        # Arrange
        user = await _seed_world(db, **kwargs)

        # Act
        manager, _chunks = await _travel(user, db, command)

        # Assert
        assert manager.state.current_scene_id == "START"
        assert manager.state.in_game_time == 0
        lines = await _system_lines(db)
    assert any(expected in line for line in lines)


@pytest.mark.asyncio
async def test_traverse_exit_adds_travel_time_and_unlocks_a_visit_point(setup_test_db, monkeypatch):
    monkeypatch.setattr(
        "backend.api.routes.adventures.turn_interactions.narrate_arrival", _no_narration
    )
    async with TestSessionLocal() as db:
        # Arrange
        user = await _seed_world(db, unlocked=())
        db.add(WorldExit(id="x3", session_id=SESSION_ID, from_scene_id="START", to_scene_id="TOWN",
                         label="a ferry", exit_type="one_way", travel_minutes=120,
                         travel_label="by ferry"))  # fmt: skip
        await db.commit()

        # Act
        manager, _chunks = await _travel(user, db, "/traverse_exit x3")

        # Assert
        assert manager.state.current_scene_id == "TOWN"
        assert manager.state.in_game_time == 120
        assert manager.clock_tick_pending is False
        assert read_travel(manager.state.entity_states)["unlocked"] == ["TOWN"]
        lines = await _system_lines(db)
    assert "The journey (by ferry) takes 2 h." in lines
    assert "Fast travel point unlocked: Town." in lines


@pytest.mark.asyncio
async def test_travel_plan_lists_points_with_route_time(setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange
        await _seed_world(db, unlocked=("TOWN", "START", "GONE"))
        manager_state = await _state(db)
        adventure = await db.get(AdventureTemplate, "adv-enc")

        # Act
        plan = await load_travel_plan(db, manager_state, adventure)

    # Assert
    points = {p["scene_id"]: p for p in plan.as_dict()["points"]}
    assert set(points) == {"TOWN", "START"}
    assert points["TOWN"]["available"] and points["TOWN"]["minutes"] == 540
    assert points["TOWN"]["hops"] == 2
    assert points["START"]["reason"] == "You are here."


async def _state(db):
    from backend.models.session_state import SessionState

    return (
        (await db.execute(select(SessionState).where(SessionState.session_id == SESSION_ID)))
        .scalars()
        .first()
    )


@pytest.mark.asyncio
async def test_crossing_a_region_border_runs_the_section_triggers(setup_test_db, monkeypatch):
    monkeypatch.setattr(
        "backend.api.routes.adventures.turn_interactions.narrate_arrival", _no_narration
    )
    async with TestSessionLocal() as db:
        # Arrange: START lies in HARBOR, ROAD in WILDS.
        user = await _seed_world(db)
        adv = await db.get(AdventureTemplate, "adv-enc")
        adv.original_manifest = {
            "scripts": [
                {"id": "LEAVE", "trigger": "on_leave_section", "target_id": "HARBOR",
                 "code": "tw.vars.set('left', 'HARBOR')"},
                {"id": "ENTER", "trigger": "on_enter_section", "target_id": "WILDS",
                 "code": "tw.vars.set('entered', 'WILDS')"},
                {"id": "OTHER", "trigger": "on_enter_section", "target_id": "HARBOR",
                 "code": "tw.vars.set('wrong', True)"},
            ]
        }  # fmt: skip
        scenes = (await db.execute(select(WorldScene))).scalars().all()
        for scene in scenes:
            scene.section_id = {"START": "HARBOR", "ROAD": "WILDS", "TOWN": "WILDS"}[scene.id]
        await db.commit()

        # Act
        manager, _chunks = await _travel(user, db, "/traverse_exit x1")

        # Assert
        script_vars = manager.state.entity_states.get("__script_vars__", {})
    assert script_vars.get("left") == "HARBOR"
    assert script_vars.get("entered") == "WILDS"
    assert "wrong" not in script_vars
