import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.agent_actions import (
    execute_agent_action,
    format_exits_for_agent,
    load_scene_exits,
)
from backend.api.routes.adventures.agent_logic import format_agent_history
from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.models.avatar import Avatar
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _seed_world(auth_client: AsyncClient) -> str:
    """Creates a session in START with an open door, a code-locked gate and a locked chest."""
    resp = await auth_client.post(
        "/api/adventures/",
        json={"title": "Agent Actions", "avatar_name": "Hero", "skip_generation": True},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    game_id = data["game_id"]

    async with TestSessionLocal() as db:
        db.add_all(
            [
                WorldScene(
                    id="START",
                    session_id=game_id,
                    label="Entrance Hall",
                    description="A dusty hall.",
                ),
                WorldScene(
                    id="LIBRARY", session_id=game_id, label="Old Library", description="Shelves."
                ),
                WorldScene(
                    id="GARDEN", session_id=game_id, label="Overgrown Garden", description="Weeds."
                ),
                WorldExit(
                    id="exit-door",
                    session_id=game_id,
                    from_scene_id="START",
                    to_scene_id="LIBRARY",
                    label="Oak Door",
                    exit_type="bidirectional",
                    is_locked=False,
                ),
                WorldExit(
                    id="exit-gate",
                    session_id=game_id,
                    from_scene_id="START",
                    to_scene_id="GARDEN",
                    label="Iron Gate",
                    is_locked=True,
                    lock_description="A keypad blinks next to the gate.",
                    code_to_unlock="4711",
                ),
                WorldEntity(
                    id="locked_chest",
                    session_id=game_id,
                    entity_type="OBJECT",
                    item_type="CONTAINER",
                    name="Locked Chest",
                    description="A locked chest.",
                    current_scene_id="START",
                    metadata_json={"item_to_unlock": "BRONZE_KEY", "locked": True},
                ),
            ]
        )
        state_res = await db.execute(select(SessionState).where(SessionState.session_id == game_id))
        state = state_res.scalars().first()
        state.current_scene_id = "START"
        state.entity_states = {**(state.entity_states or {}), "locked_chest": {"locked": True}}
        flag_modified(state, "entity_states")

        avatar_res = await db.execute(select(Avatar).where(Avatar.id == data["avatar_id"]))
        avatar = avatar_res.scalars().first()
        avatar.inventory = [{"id": "BRONZE_KEY", "name": "Bronze Key", "item_type": "PICKABLE"}]
        flag_modified(avatar, "inventory")
        await db.commit()
    return game_id


async def _manager(db, game_id: str) -> GameTurnManager:
    user = (await db.execute(select(User).limit(1))).scalars().first()
    manager = GameTurnManager(db, game_id, user)
    assert await manager.initialize()
    return manager


async def test_go_resolves_exit_label_and_destination(auth_client, setup_test_db):
    game_id = await _seed_world(auth_client)
    async with TestSessionLocal() as db:
        manager = await _manager(db, game_id)

        by_label = await execute_agent_action(manager, "/go oak door")
        by_destination = await execute_agent_action(manager, "/go Old Library")

    assert by_label.turn_command == "/traverse_exit exit-door"
    assert by_destination.turn_command == "/traverse_exit exit-door"


async def test_go_reports_locked_and_unknown_exits(auth_client, setup_test_db):
    game_id = await _seed_world(auth_client)
    async with TestSessionLocal() as db:
        manager = await _manager(db, game_id)

        locked = await execute_agent_action(manager, "/go Iron Gate")
        unknown = await execute_agent_action(manager, "/go north")

    assert locked.turn_command is None
    assert "locked" in locked.message
    assert "/unlock Iron Gate code" in locked.message
    assert unknown.turn_command is None
    assert "Oak Door" in unknown.message


async def test_unlock_exit_with_code(auth_client, setup_test_db):
    game_id = await _seed_world(auth_client)
    async with TestSessionLocal() as db:
        manager = await _manager(db, game_id)

        wrong = await execute_agent_action(manager, "/unlock Iron Gate code 1234")
        right = await execute_agent_action(manager, "/unlock Iron Gate code 4711")

    assert "failed" in wrong.message
    assert "now unlocked" in right.message
    async with TestSessionLocal() as db:
        gate = (await db.execute(select(WorldExit).where(WorldExit.id == "exit-gate"))).scalar_one()
        assert gate.is_locked is False


async def test_unlock_container_with_inventory_item(auth_client, setup_test_db):
    game_id = await _seed_world(auth_client)
    async with TestSessionLocal() as db:
        manager = await _manager(db, game_id)

        missing = await execute_agent_action(manager, "/unlock Locked Chest with Silver Key")
        outcome = await execute_agent_action(manager, "/unlock chest with bronze key")

    assert "not carrying" in missing.message
    assert "now unlocked" in outcome.message
    async with TestSessionLocal() as db:
        state_res = await db.execute(select(SessionState).where(SessionState.session_id == game_id))
        assert state_res.scalars().first().entity_states["locked_chest"]["locked"] is False


async def test_regular_actions_pass_through(auth_client, setup_test_db):
    game_id = await _seed_world(auth_client)
    async with TestSessionLocal() as db:
        manager = await _manager(db, game_id)
        outcome = await execute_agent_action(manager, "/inspect desk")

    assert outcome.turn_command == "/inspect desk"


async def test_exit_list_tells_agent_how_to_move_and_unlock(auth_client, setup_test_db):
    game_id = await _seed_world(auth_client)
    async with TestSessionLocal() as db:
        text = format_exits_for_agent(await load_scene_exits(db, game_id, "START"))

    assert "Oak Door -> leads to Old Library [OPEN] -> `/go Oak Door`" in text
    assert "Iron Gate -> leads to Overgrown Garden [LOCKED" in text
    assert "`/unlock Iron Gate code <code>`" in text
    assert "4711" not in text


def test_agent_history_skips_thoughts_and_truncates():
    history = [
        {"role": "assistant", "content": "You stand in a dusty hall."},
        {"role": "thought", "content": "secret reasoning"},
        {"role": "player", "content": "/go Oak Door"},
        {"role": "system", "content": "x" * 1000},
    ]

    text = format_agent_history(history)

    assert "GAME MASTER: You stand in a dusty hall." in text
    assert "YOU: /go Oak Door" in text
    assert "secret reasoning" not in text
    assert text.endswith("...")
    assert format_agent_history([]).startswith("(no history yet")
