# pyright: reportUnusedParameter=false, reportUnusedVariable=false
# pylint: disable=unused-argument,unused-variable
# ruff: noqa: ARG001,F841

"""Tests for the CONSTRUCTABLE item type.

Covers:
- Structural validation (backend.core.world_validator)
- Deterministic engine resolution (GameTurnManager._enforce_constructable_combination)
"""

import pytest

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.core.world_validator import validate_adventure
from backend.engine.rule_engine import GameEvent
from backend.models.avatar import Avatar
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.adventure_template import AdventureTemplate
from backend.models.world_entity import WorldEntity

pytestmark = pytest.mark.asyncio


def _payload(objects):
    return {
        "adventure": {"id": "adv", "start_scene_id": "START", "title": "T", "teaser": "x"},
        "scenes": [{"id": "START", "label": "Start", "description": "A room."}],
        "npcs": [],
        "objects": objects,
        "exits": [],
    }


# ---------------------------------------------------------------------------
# Structural validation
# ---------------------------------------------------------------------------


def _codes(findings):
    return [(f.severity, f.code) for f in findings]


def test_constructable_valid_when_hidden_with_two_ingredients():
    payload = _payload([
        {"id": "BATTERY", "entity_type": "OBJECT", "item_type": "DEFAULT", "name": "Battery", "is_hidden": False},
        {"id": "TORCH", "entity_type": "OBJECT", "item_type": "DEFAULT", "name": "Torch", "is_hidden": False},
        {
            "id": "LANTERN",
            "entity_type": "OBJECT",
            "item_type": "CONSTRUCTABLE",
            "name": "Lantern",
            "is_hidden": True,
            "combination_ingredients": ["BATTERY", "TORCH"],
        },
    ])
    findings = [f for f in validate_adventure(payload) if f.code.startswith("constructable")]
    assert findings == []


def test_constructable_needs_at_least_two_ingredients():
    payload = _payload([
        {"id": "BATTERY", "entity_type": "OBJECT", "item_type": "DEFAULT", "name": "Battery"},
        {
            "id": "LANTERN",
            "entity_type": "OBJECT",
            "item_type": "CONSTRUCTABLE",
            "name": "Lantern",
            "is_hidden": True,
            "combination_ingredients": ["BATTERY"],
        },
    ])
    findings = validate_adventure(payload)
    assert ("error", "constructable_needs_ingredients") in _codes(findings)


def test_constructable_missing_ingredient_reference():
    payload = _payload([
        {"id": "BATTERY", "entity_type": "OBJECT", "item_type": "DEFAULT", "name": "Battery"},
        {
            "id": "LANTERN",
            "entity_type": "OBJECT",
            "item_type": "CONSTRUCTABLE",
            "name": "Lantern",
            "is_hidden": True,
            "combination_ingredients": ["BATTERY", "GHOST"],
        },
    ])
    findings = validate_adventure(payload)
    assert ("error", "constructable_ingredient_missing") in _codes(findings)


def test_constructable_should_be_hidden_warns():
    payload = _payload([
        {"id": "BATTERY", "entity_type": "OBJECT", "item_type": "DEFAULT", "name": "Battery"},
        {"id": "TORCH", "entity_type": "OBJECT", "item_type": "DEFAULT", "name": "Torch"},
        {
            "id": "LANTERN",
            "entity_type": "OBJECT",
            "item_type": "CONSTRUCTABLE",
            "name": "Lantern",
            "is_hidden": False,
            "combination_ingredients": ["BATTERY", "TORCH"],
        },
    ])
    findings = validate_adventure(payload)
    assert ("warn", "constructable_not_hidden") in _codes(findings)


# ---------------------------------------------------------------------------
# Engine deterministic resolution
# ---------------------------------------------------------------------------


async def _seed(db):
    user = User(username="player1", hashed_password="pw", role="user")
    adv = AdventureTemplate(id="adv-1", title="Test", owner_id="admin", time_per_turn=5, strict_rules=True)
    db.add_all([user, adv])
    await db.flush()
    avatar = Avatar(
        id="av-1",
        template_id=adv.id,
        user_id=user.id,
        name="Hero",
        role="Warrior",
        hp=100,
        stats={"strength": 10, "dexterity": 10},
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
    await db.commit()
    return user, adv, avatar, state


async def test_constructable_materializes_when_all_ingredients_combined(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, avatar, state = await _seed(db)

        # Two ingredients in the player's inventory.
        db.add(WorldEntity(id="BATTERY", session_id=state.session_id, entity_type="OBJECT",
                           item_type="DEFAULT", name="Battery", description="A battery.", current_scene_id="START",
                           is_hidden=False, is_in_inventory=True))
        db.add(WorldEntity(id="TORCH", session_id=state.session_id, entity_type="OBJECT",
                           item_type="DEFAULT", name="Torch", description="A torch.", current_scene_id="START",
                           is_hidden=False, is_in_inventory=True))
        # Hidden constructable result.
        db.add(WorldEntity(id="LANTERN", session_id=state.session_id, entity_type="OBJECT",
                           item_type="CONSTRUCTABLE", name="Lantern", description="A lantern.", current_scene_id="START",
                           is_hidden=True, combination_ingredients=["BATTERY", "TORCH"]))
        await db.commit()

        avatar.inventory = [
            {"id": "BATTERY", "name": "Battery"},
            {"id": "TORCH", "name": "Torch"},
        ]
        await db.commit()

        manager = GameTurnManager(db, state.session_id, user)
        await manager.initialize()

        event = GameEvent()
        messages = await manager._enforce_constructable_combination(event, "combine battery with torch")

        assert any("create" in m.lower() for m in messages)
        # Ingredients scheduled for removal from inventory.
        assert set(event.removed_inventory_item_ids or []) == {"BATTERY", "TORCH"}
        # Constructable revealed in current scene.
        reveal = next(u for u in event.updated_entities if u.entity_id == "LANTERN")
        assert reveal.is_hidden is False
        assert any(m.entity_id == "LANTERN" and m.to_scene_id == "START" for m in (event.moved_entities or []))


async def test_constructable_noop_when_ingredient_missing(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, avatar, state = await _seed(db)

        db.add(WorldEntity(id="BATTERY", session_id=state.session_id, entity_type="OBJECT",
                           item_type="DEFAULT", name="Battery", description="A battery.", current_scene_id="START",
                           is_hidden=False, is_in_inventory=True))
        db.add(WorldEntity(id="TORCH", session_id=state.session_id, entity_type="OBJECT",
                           item_type="DEFAULT", name="Torch", description="A torch.", current_scene_id="START",
                           is_hidden=False, is_in_inventory=True))
        db.add(WorldEntity(id="LANTERN", session_id=state.session_id, entity_type="OBJECT",
                           item_type="CONSTRUCTABLE", name="Lantern", description="A lantern.", current_scene_id="START",
                           is_hidden=True, combination_ingredients=["BATTERY", "TORCH"]))
        await db.commit()

        # Player only carries one of two ingredients.
        avatar.inventory = [{"id": "BATTERY", "name": "Battery"}]
        await db.commit()

        manager = GameTurnManager(db, state.session_id, user)
        await manager.initialize()

        event = GameEvent()
        messages = await manager._enforce_constructable_combination(event, "combine battery with torch")

        assert messages == []
        assert not event.removed_inventory_item_ids
        assert not event.updated_entities


async def test_constructable_noop_when_already_revealed(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, avatar, state = await _seed(db)

        db.add(WorldEntity(id="BATTERY", session_id=state.session_id, entity_type="OBJECT",
                           item_type="DEFAULT", name="Battery", description="A battery.", current_scene_id="START",
                           is_hidden=False, is_in_inventory=True))
        db.add(WorldEntity(id="TORCH", session_id=state.session_id, entity_type="OBJECT",
                           item_type="DEFAULT", name="Torch", description="A torch.", current_scene_id="START",
                           is_hidden=False, is_in_inventory=True))
        # Already visible -> should not re-trigger.
        db.add(WorldEntity(id="LANTERN", session_id=state.session_id, entity_type="OBJECT",
                           item_type="CONSTRUCTABLE", name="Lantern", description="A lantern.", current_scene_id="START",
                           is_hidden=False, combination_ingredients=["BATTERY", "TORCH"]))
        await db.commit()

        avatar.inventory = [
            {"id": "BATTERY", "name": "Battery"},
            {"id": "TORCH", "name": "Torch"},
        ]
        await db.commit()

        manager = GameTurnManager(db, state.session_id, user)
        await manager.initialize()

        event = GameEvent()
        messages = await manager._enforce_constructable_combination(event, "combine battery with torch")

        assert messages == []
        assert not event.removed_inventory_item_ids


async def test_constructable_noop_without_combine_intent(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, avatar, state = await _seed(db)

        db.add(WorldEntity(id="BATTERY", session_id=state.session_id, entity_type="OBJECT",
                           item_type="DEFAULT", name="Battery", description="A battery.", current_scene_id="START",
                           is_hidden=False, is_in_inventory=True))
        db.add(WorldEntity(id="TORCH", session_id=state.session_id, entity_type="OBJECT",
                           item_type="DEFAULT", name="Torch", description="A torch.", current_scene_id="START",
                           is_hidden=False, is_in_inventory=True))
        db.add(WorldEntity(id="LANTERN", session_id=state.session_id, entity_type="OBJECT",
                           item_type="CONSTRUCTABLE", name="Lantern", description="A lantern.", current_scene_id="START",
                           is_hidden=True, combination_ingredients=["BATTERY", "TORCH"]))
        await db.commit()

        avatar.inventory = [
            {"id": "BATTERY", "name": "Battery"},
            {"id": "TORCH", "name": "Torch"},
        ]
        await db.commit()

        manager = GameTurnManager(db, state.session_id, user)
        await manager.initialize()

        event = GameEvent()
        # Unrelated action — must not trigger construction even though ingredients are carried.
        messages = await manager._enforce_constructable_combination(event, "look around the room")

        assert messages == []
        assert not event.removed_inventory_item_ids


async def test_constructable_consumes_scene_ingredient(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, avatar, state = await _seed(db)

        # One ingredient in inventory, one visible in the scene.
        db.add(WorldEntity(id="BATTERY", session_id=state.session_id, entity_type="OBJECT",
                           item_type="DEFAULT", name="Battery", description="A battery.", current_scene_id="START",
                           is_hidden=False, is_in_inventory=True))
        db.add(WorldEntity(id="TORCH", session_id=state.session_id, entity_type="OBJECT",
                           item_type="DEFAULT", name="Torch", description="A torch.", current_scene_id="START",
                           is_hidden=False, is_in_inventory=False))
        db.add(WorldEntity(id="LANTERN", session_id=state.session_id, entity_type="OBJECT",
                           item_type="CONSTRUCTABLE", name="Lantern", description="A lantern.", current_scene_id="START",
                           is_hidden=True, combination_ingredients=["BATTERY", "TORCH"]))
        await db.commit()

        avatar.inventory = [{"id": "BATTERY", "name": "Battery"}]
        await db.commit()

        manager = GameTurnManager(db, state.session_id, user)
        await manager.initialize()

        event = GameEvent()
        messages = await manager._enforce_constructable_combination(event, "use battery on torch")

        assert any("create" in m.lower() for m in messages)
        # Inventory ingredient removed.
        assert event.removed_inventory_item_ids == ["BATTERY"]
        # Scene ingredient hidden.
        torch_update = next(u for u in event.updated_entities if u.entity_id == "TORCH")
        assert torch_update.is_hidden is True
        # Result revealed.
        reveal = next(u for u in event.updated_entities if u.entity_id == "LANTERN")
        assert reveal.is_hidden is False


async def test_constructable_reverts_illegal_spawn(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, avatar, state = await _seed(db)

        db.add(WorldEntity(id="BATTERY", session_id=state.session_id, entity_type="OBJECT",
                           item_type="DEFAULT", name="Battery", description="A battery.", current_scene_id="START",
                           is_hidden=False, is_in_inventory=True))
        db.add(WorldEntity(id="TORCH", session_id=state.session_id, entity_type="OBJECT",
                           item_type="DEFAULT", name="Torch", description="A torch.", current_scene_id="START",
                           is_hidden=False, is_in_inventory=True))
        db.add(WorldEntity(id="LANTERN", session_id=state.session_id, entity_type="OBJECT",
                           item_type="CONSTRUCTABLE", name="Lantern", description="A lantern.", current_scene_id="START",
                           is_hidden=True, combination_ingredients=["BATTERY", "TORCH"]))
        await db.commit()

        manager = GameTurnManager(db, state.session_id, user)
        await manager.initialize()

        # The LLM outputs schema updates trying to illegally add/unhide the lantern.
        from backend.engine.rule_engine import InventoryItem, WorldEntityUpdate
        event = GameEvent(
            new_inventory_items=[InventoryItem(id="LANTERN", name="Lantern")],
            updated_entities=[WorldEntityUpdate(entity_id="LANTERN", is_hidden=False)]
        )

        messages = await manager._enforce_constructable_combination(event, "look at lantern")

        # The lantern should be removed from new_inventory_items and updated_entities updates.
        assert not event.new_inventory_items
        assert not event.updated_entities
        assert any("Rule Violation" in m for m in messages)

