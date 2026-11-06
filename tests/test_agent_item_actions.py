import pytest
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.agent_actions import execute_agent_action
from backend.api.routes.adventures.agent_change_log import describe_changes, take_snapshot
from backend.api.routes.adventures.agent_world_view import (
    format_room_objects,
    load_room_entities,
    opened_container_ids,
)
from backend.models.avatar import Avatar
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldEntity
from tests.conftest import TestSessionLocal
from tests.test_agent_actions import _manager, _seed_world

pytestmark = pytest.mark.asyncio


async def _seed_room(auth_client) -> str:
    """Adds an open chest with a key, a guard and a lever to the agent test world."""
    game_id = await _seed_world(auth_client)
    async with TestSessionLocal() as db:
        db.add_all(
            [
                WorldEntity(
                    id="SILVER_KEY",
                    session_id=game_id,
                    entity_type="OBJECT",
                    item_type="KEY",
                    name="Silver Key",
                    description="A test entity.",
                    current_scene_id="START",
                ),
                WorldEntity(
                    id="OLD_CHEST",
                    session_id=game_id,
                    entity_type="OBJECT",
                    item_type="CONTAINER",
                    name="Old Chest",
                    description="A test entity.",
                    current_scene_id="START",
                    inventory=["SILVER_KEY"],
                    metadata_json={"locked": False},
                ),
                WorldEntity(
                    id="GUARD",
                    session_id=game_id,
                    entity_type="NPC",
                    name="Tired Guard",
                    description="A test entity.",
                    current_scene_id="START",
                ),
                WorldEntity(
                    id="LEVER",
                    session_id=game_id,
                    entity_type="OBJECT",
                    item_type="SWITCH",
                    name="Big Lever",
                    description="A test entity.",
                    current_scene_id="START",
                    metadata_json={
                        "switch": {
                            "states": ["UP", "DOWN"],
                            "initial_state": "UP",
                            "state_labels": {"DOWN": "Pulled down"},
                        }
                    },
                ),
            ]
        )
        await db.commit()
    return game_id


async def test_take_from_container_resolves_names_and_remembers_opening(auth_client, setup_test_db):
    game_id = await _seed_room(auth_client)
    async with TestSessionLocal() as db:
        manager = await _manager(db, game_id)

        outcome = await execute_agent_action(manager, "/take silver key from the chest")

        assert outcome.turn_command == "/container_take_item Old Chest | Silver Key"
        agent_state = manager.state.entity_states["__agent__"]
        assert "OLD_CHEST" in opened_container_ids(agent_state)


async def test_plain_take_and_unknown_container_pass_through(auth_client, setup_test_db):
    game_id = await _seed_room(auth_client)
    async with TestSessionLocal() as db:
        manager = await _manager(db, game_id)

        plain = await execute_agent_action(manager, "/take Silver Key")
        from_npc = await execute_agent_action(manager, "/take coin from the guard")

    assert plain.turn_command == "/take Silver Key"
    assert from_npc.turn_command == "/take coin from the guard"


async def test_put_and_give_use_exact_inventory_names(auth_client, setup_test_db):
    game_id = await _seed_room(auth_client)
    async with TestSessionLocal() as db:
        manager = await _manager(db, game_id)

        put = await execute_agent_action(manager, "/put bronze key into old chest")
        give = await execute_agent_action(manager, "/give the bronze key to guard")
        nobody = await execute_agent_action(manager, "/give bronze key to the king")

    assert put.turn_command == "/container_put_items Old Chest | Bronze Key"
    assert give.turn_command == "/give_items GUARD | Bronze Key"
    assert nobody.turn_command is None
    assert "Tired Guard" in nobody.message


async def test_switch_accepts_names_with_spaces_and_state_labels(auth_client, setup_test_db):
    game_id = await _seed_room(auth_client)
    async with TestSessionLocal() as db:
        manager = await _manager(db, game_id)

        by_id = await execute_agent_action(manager, "/switch big lever down")
        by_label = await execute_agent_action(manager, '/switch "Big Lever" pulled down')
        bad_state = await execute_agent_action(manager, "/switch big lever sideways")
        unknown = await execute_agent_action(manager, "/switch crank up")

    assert by_id.turn_command == '/switch "LEVER" DOWN'
    assert by_label.turn_command == '/switch "LEVER" DOWN'
    assert "UP, DOWN" in bad_state.message
    assert "Big Lever" in unknown.message


async def test_room_view_lists_switch_states_and_contents_after_opening(auth_client, setup_test_db):
    game_id = await _seed_room(auth_client)
    async with TestSessionLocal() as db:
        manager = await _manager(db, game_id)
        room = await load_room_entities(db, manager.state)

        closed = format_room_objects(room, set())
        opened = format_room_objects(room, {"OLD_CHEST"})

    assert "Old Chest (container, closed -> look inside with `/open Old Chest`)" in closed
    assert "Silver Key" not in closed
    assert "contains: Silver Key" in opened
    assert "Big Lever (switch, currently UP [UP]; can be set to: DOWN (Pulled down)" in closed
    assert "Locked Chest (container, LOCKED" in closed
    assert "BRONZE_KEY" not in closed


async def test_change_log_reports_items_switches_and_unlocks(auth_client, setup_test_db):
    game_id = await _seed_room(auth_client)
    async with TestSessionLocal() as db:
        state = (
            await db.execute(select(SessionState).where(SessionState.session_id == game_id))
        ).scalar_one()
        avatar = await db.get(Avatar, state.avatar_id)
        before = await take_snapshot(db, game_id, avatar.id)

        avatar.inventory = [*avatar.inventory, {"id": "SILVER_KEY", "name": "Silver Key"}]
        flag_modified(avatar, "inventory")
        state.entity_states = {
            **state.entity_states,
            "LEVER": {"switch_state": "DOWN"},
            "locked_chest": {"locked": False},
        }
        flag_modified(state, "entity_states")
        await db.commit()

        message = await describe_changes(db, game_id, before)
        unchanged = await describe_changes(db, game_id, await take_snapshot(db, game_id, avatar.id))

    assert message.startswith("Play-Agent changes:")
    assert "- Received: Silver Key" in message
    assert "- Big Lever: UP -> Pulled down" in message
    assert "- Unlocked: Locked Chest" in message
    assert unchanged == ""


async def test_agent_settings_store_step_delay_and_tts_wait(auth_client, setup_test_db):
    game_id = await _seed_world(auth_client)

    resp = await auth_client.patch(
        f"/api/adventures/{game_id}/agent/settings",
        json={"step_delay": 10, "wait_for_tts": True},
    )
    too_long = await auth_client.patch(
        f"/api/adventures/{game_id}/agent/settings", json={"step_delay": 9999}
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["agent_step_delay"] == 10
    assert resp.json()["agent_wait_for_tts"] is True
    assert too_long.status_code == 422
