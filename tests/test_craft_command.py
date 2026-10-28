"""Tests for deterministic crafting via ``/craft A | B`` (the in-game combine panel)."""

import pytest

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.api.routes.adventures.guardrails.crafting import (
    CRAFT_NO_MATCH_MESSAGE,
    CRAFT_TOO_FEW_MESSAGE,
    CRAFT_UNREACHABLE_MESSAGE,
)
from backend.engine.command_parser import CommandParser
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity

pytestmark = pytest.mark.asyncio


def _object(entity_id: str, name: str, **fields) -> WorldEntity:
    defaults = {
        "session_id": "session-1",
        "entity_type": "OBJECT",
        "item_type": "DEFAULT",
        "description": f"A {name.lower()}.",
        "current_scene_id": "START",
        "is_hidden": False,
        "is_in_inventory": False,
    }
    return WorldEntity(id=entity_id, name=name, **{**defaults, **fields})


async def _seed(db, *, battery_in_inventory: bool = True, lantern_meta: dict | None = None):
    user = User(username="player1", hashed_password="pw", role="user")
    adv = AdventureTemplate(id="adv-1", title="Test", owner_id="admin", time_per_turn=5)
    db.add_all([user, adv])
    await db.flush()
    avatar = Avatar(
        id="av-1",
        template_id=adv.id,
        user_id=user.id,
        name="Hero",
        role="Warrior",
        hp=100,
        stats={"strength": 10},
    )
    db.add(avatar)
    await db.flush()
    state = SessionState(
        session_id="session-1",
        template_id=adv.id,
        avatar_id=avatar.id,
        user_id=user.id,
        current_scene_id="START",
        in_game_time=0,
    )
    db.add(state)
    db.add_all(
        [
            _object("BATTERY", "Battery", is_in_inventory=battery_in_inventory),
            _object("TORCH", "Torch", is_in_inventory=True),
            _object("ROPE", "Rope", is_in_inventory=True),
            _object("FAR_AWAY", "Far Away Gear", current_scene_id="ELSEWHERE"),
            _object("LANTERN", "Lantern", is_hidden=True, image_url="/data/lantern.png"),
            _object(
                "LANTERN_RECIPE",
                "Lantern recipe",
                item_type="CONSTRUCTABLE",
                is_hidden=True,
                combination_ingredients=["BATTERY", "TORCH"],
                metadata_json={"result_item_ids": ["LANTERN"], **(lantern_meta or {})},
            ),
        ]
    )
    inventory = [{"id": "TORCH", "name": "Torch"}, {"id": "ROPE", "name": "Rope"}]
    if battery_in_inventory:
        inventory.append({"id": "BATTERY", "name": "Battery"})
    avatar.inventory = inventory
    await db.commit()
    return user, avatar, state


async def _manager(db, user) -> GameTurnManager:
    manager = GameTurnManager(db, "session-1", user)
    await manager.initialize()
    return manager


def _inventory_ids(avatar: Avatar) -> set[str]:
    return {item["id"] for item in avatar.inventory or [] if isinstance(item, dict)}


async def test_craft_command_maps_to_trigger():
    # Arrange / Act
    response = CommandParser.parse_command(Avatar(name="Hero"), "/craft BATTERY | TORCH")

    # Assert
    assert response == "[TRIGGER_CRAFT] BATTERY | TORCH"


async def test_craft_exact_ingredients_creates_item(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        # Arrange
        user, avatar, state = await _seed(db)
        manager = await _manager(db, user)

        # Act
        messages, _applied = await manager.guardrails._craft_selected("battery | Torch")

        # Assert: crafted into the inventory, so it is not moved into the scene.
        assert len(messages) == 1
        assert "Lantern" in messages[0]
        assert "current_scene_id" not in manager.state.entity_states["LANTERN"]
        assert _inventory_ids(manager.avatar) == {"ROPE", "LANTERN"}
        lantern = next(i for i in manager.avatar.inventory if i["id"] == "LANTERN")
        assert lantern["image_url"] == "/data/lantern.png"
        assert manager.state.entity_states["LANTERN"]["is_hidden"] is False


async def test_craft_uses_scene_ingredient(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        # Arrange: the battery lies in the scene, the torch is carried.
        user, _avatar, _state = await _seed(db, battery_in_inventory=False)
        manager = await _manager(db, user)

        # Act
        messages, _applied = await manager.guardrails._craft_selected("BATTERY | TORCH")

        # Assert: the result appears in the scene; the scene ingredient is hidden.
        assert "Lantern" in messages[0]
        assert "LANTERN" not in _inventory_ids(manager.avatar)
        assert manager.state.entity_states["BATTERY"]["is_hidden"] is True
        assert manager.state.entity_states["LANTERN"]["is_hidden"] is False


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        ("BATTERY", CRAFT_TOO_FEW_MESSAGE),
        ("BATTERY | FAR_AWAY", CRAFT_UNREACHABLE_MESSAGE),
        ("BATTERY | ROPE", CRAFT_NO_MATCH_MESSAGE),
        ("BATTERY | TORCH | ROPE", CRAFT_NO_MATCH_MESSAGE),
    ],
)
async def test_craft_rejects_without_consuming(setup_test_db, args, expected):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        # Arrange
        user, _avatar, _state = await _seed(db)
        manager = await _manager(db, user)

        # Act
        messages, applied = await manager.guardrails._craft_selected(args)

        # Assert: wrong or extra items fail and nothing is used up.
        assert messages == [expected]
        assert applied == []
        assert _inventory_ids(manager.avatar) == {"BATTERY", "TORCH", "ROPE"}
        assert "LANTERN" not in (manager.state.entity_states or {})


async def test_craft_success_text_replaces_default_message(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        # Arrange
        user, _avatar, _state = await _seed(
            db, lantern_meta={"on_craft_success_text": "The lantern flickers to life."}
        )
        manager = await _manager(db, user)

        # Act
        messages, _applied = await manager.guardrails._craft_selected("BATTERY | TORCH")

        # Assert
        assert messages == ["The lantern flickers to life."]


async def test_craft_failure_text_replaces_default_guard_message(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        # Arrange: a craft guard that never passes.
        user, _avatar, _state = await _seed(
            db,
            lantern_meta={
                "craft_guard_expression": "False",
                "on_craft_failure_text": "Your hands are too cold.",
            },
        )
        manager = await _manager(db, user)

        # Act
        messages, applied = await manager.guardrails._craft_selected("BATTERY | TORCH")

        # Assert: nothing is consumed and only the custom text is shown.
        assert messages == ["Your hands are too cold."]
        assert applied == []
        assert _inventory_ids(manager.avatar) == {"BATTERY", "TORCH", "ROPE"}
