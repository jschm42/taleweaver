"""The play-agent's known map and the `/travel` command."""

from types import SimpleNamespace

from backend.api.routes.adventures import agent_travel
from backend.api.routes.adventures.agent_known_map import (
    build_known_map,
    find_route,
    format_known_map,
    match_place,
)
from backend.api.routes.adventures.agent_travel import (
    TRAVEL_KEY,
    next_travel_step,
    set_travel_target,
    travel,
)
from backend.models.session_state import SessionState

LABELS = {
    "HALL": "Great Hall",
    "LIB": "Library",
    "CELLAR": "Cellar",
    "TOWER": "Tower",
    "VAULT": "Vault",
}


def _exit(exit_id, src, dst, label="", locked=False, two_way=True, hidden=False):
    return SimpleNamespace(
        id=exit_id,
        from_scene_id=src,
        to_scene_id=dst,
        label=label,
        is_locked=locked,
        is_hidden=hidden,
        exit_type="bidirectional" if two_way else "directional",
        code_to_unlock="1234",
        item_to_unlock="SECRET_KEY",
    )


EXITS = [
    _exit("E1", "HALL", "LIB", "Oak Door"),
    _exit("E2", "LIB", "CELLAR", "Trapdoor"),
    _exit("E3", "HALL", "TOWER", "Spiral Stairs", locked=True),
    _exit("E4", "CELLAR", "VAULT", "Iron Gate"),
    _exit("E5", "LIB", "HALL", "Secret Passage", hidden=True),
]


def _known(current="CELLAR", visited=("HALL", "LIB", "CELLAR")):
    return build_known_map(current, [current, *visited], EXITS, LABELS)


def test_map_lists_visited_places_without_secrets_or_hidden_exits():
    text = format_known_map(_known())

    assert "Cellar (YOU ARE HERE)" in text
    assert "Oak Door -> Library [OPEN]" in text
    assert "Spiral Stairs -> unexplored [LOCKED]" in text
    assert "Iron Gate -> unexplored [OPEN]" in text
    assert "Vault" not in text and "Tower" not in text  # never visited: no names
    assert "1234" not in text and "SECRET_KEY" not in text
    assert "Secret Passage" not in text


def test_route_uses_open_exits_between_visited_places():
    known = _known()

    route = find_route(known, "HALL")

    assert [step.exit_id for step in route] == ["E2", "E1"]
    assert find_route(known, "CELLAR") == []


def test_no_route_through_locked_or_unvisited_places():
    known = _known(current="HALL", visited=("HALL", "TOWER"))

    assert find_route(known, "TOWER") is None  # only the locked stairs lead there


def test_places_match_by_name_or_id():
    known = _known()

    assert match_place(known, "library") == "LIB"
    assert match_place(known, "great") == "HALL"
    assert match_place(known, "vault") is None  # never visited


def _manager(current="CELLAR"):
    state = SessionState(current_scene_id=current, entity_states={"__agent__": {}})
    return SimpleNamespace(state=state, db=None, game_id="G1")


def _patch_map(monkeypatch, current="CELLAR"):
    async def fake_load(_db, _game_id, state):
        return build_known_map(state.current_scene_id, ["HALL", "LIB", "CELLAR"], EXITS, LABELS)

    monkeypatch.setattr(agent_travel, "load_known_map", fake_load)


async def test_travel_takes_the_first_exit_and_remembers_the_goal(monkeypatch):
    _patch_map(monkeypatch)
    manager = _manager()

    outcome = await travel(manager, "Great Hall")

    assert outcome.turn_command == "/traverse_exit E2"
    assert manager.state.entity_states["__agent__"][TRAVEL_KEY] == "HALL"


async def test_next_step_continues_until_arrival(monkeypatch):
    _patch_map(monkeypatch)
    manager = _manager(current="LIB")
    set_travel_target(manager.state, "HALL")

    thought, action = await next_travel_step(manager)
    last = await travel(manager, action.removeprefix("/travel "))

    assert action == "/travel Great Hall"
    assert "Great Hall" in thought
    assert last.turn_command == "/traverse_exit E1"
    assert TRAVEL_KEY not in manager.state.entity_states["__agent__"]  # last step arrives


async def test_unknown_or_blocked_places_explain_why(monkeypatch):
    _patch_map(monkeypatch)
    manager = _manager()

    unknown = await travel(manager, "Vault")
    here = await travel(manager, "Cellar")

    assert unknown.turn_command is None
    assert "Known places: Great Hall, Library" in unknown.message
    assert "already in Cellar" in here.message
    assert await next_travel_step(manager) is None


async def test_known_map_reaches_the_agent_prompt(setup_test_db, monkeypatch):
    from backend.api.routes.adventures.agent_logic import AgentService
    from backend.models.avatar import Avatar
    from tests.conftest import TestSessionLocal
    from tests.test_agent_player_mode import _fake_llm, _start

    captured: dict[str, str] = {}
    _fake_llm(monkeypatch, captured)

    async with TestSessionLocal() as db:
        user, adv, state = await _start(db, "agent-known-map", "agent_known_map")
        avatar = await db.get(Avatar, state.avatar_id)
        await AgentService.get_decision(
            db, state.session_id, user, state, avatar, adv, SimpleNamespace()
        )

    assert "KNOWN MAP" in captured["system_prompt"]
    assert "/travel <place>" in captured["system_prompt"]


async def test_running_trip_needs_no_llm_decision(monkeypatch):
    from backend.api.routes.adventures import agent_turn_stream

    async def fake_step(_manager):
        return "On my way to Library.", "/travel Library"

    async def no_llm(*_args, **_kwargs):
        raise AssertionError("the LLM must not be asked during a trip")

    monkeypatch.setattr(agent_turn_stream, "next_travel_step", fake_step)
    monkeypatch.setattr(agent_turn_stream.AgentService, "get_decision", no_llm)
    manager = SimpleNamespace(_has_combat_phase=lambda: False)

    decision, failed = await agent_turn_stream._decide(None, "G1", None, manager)

    assert failed is False
    assert decision.action == "/travel Library"
