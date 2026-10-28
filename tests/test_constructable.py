# pyright: reportUnusedParameter=false
# ruff: noqa: ARG001

"""Tests for CONSTRUCTABLE recipes (meta items that turn ingredients into result items).

Covers:
- Structural validation (backend.core.world_validator)
- Deterministic engine resolution (GameTurnManager._enforce_constructable_combination)
- Recipe visibility (never shown in the world)
"""

import pytest

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.api.routes.adventures.logic import _merge_session_entity
from backend.core.world_validator import validate_adventure
from backend.engine.manifest_apply.objects import recipe_result_ids, starts_hidden
from backend.engine.rule_engine import GameEvent, InventoryItem, WorldEntityUpdate
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Structural validation
# ---------------------------------------------------------------------------


def _payload(objects):
    return {
        "adventure": {"id": "adv", "start_scene_id": "START", "title": "T", "teaser": "x"},
        "scenes": [{"id": "START", "label": "Start", "description": "A room."}],
        "npcs": [],
        "objects": objects,
        "exits": [],
    }


def _obj(eid: str, item_type: str = "DEFAULT", **fields):
    return {
        "id": eid,
        "entity_type": "OBJECT",
        "item_type": item_type,
        "name": eid.title(),
        **fields,
    }


def _recipe(**fields):
    defaults = {
        "combination_ingredients": ["BATTERY", "TORCH"],
        "result_item_ids": ["LANTERN"],
        "is_hidden": True,
    }
    return _obj("LANTERN_RECIPE", "CONSTRUCTABLE", **{**defaults, **fields})


def _ingredients_and_result(result_type: str = "SWITCH", hidden: bool = True):
    return [_obj("BATTERY"), _obj("TORCH"), _obj("LANTERN", result_type, is_hidden=hidden)]


def _recipe_codes(objects):
    return [
        (f.severity, f.code)
        for f in validate_adventure(_payload(objects))
        if f.code.startswith("constructable")
    ]


async def test_recipe_valid_with_hidden_result_of_any_type():
    # Arrange
    objects = [*_ingredients_and_result("SWITCH"), _recipe(kept_ingredients=["TORCH"])]

    # Act / Assert
    assert _recipe_codes(objects) == []


async def test_recipe_needs_at_least_two_ingredients():
    objects = [*_ingredients_and_result(), _recipe(combination_ingredients=["BATTERY"])]

    assert ("error", "constructable_needs_ingredients") in _recipe_codes(objects)


async def test_recipe_missing_ingredient_reference():
    objects = [*_ingredients_and_result(), _recipe(combination_ingredients=["BATTERY", "GHOST"])]

    assert ("error", "constructable_ingredient_missing") in _recipe_codes(objects)


async def test_recipe_needs_a_result():
    objects = [*_ingredients_and_result(), _recipe(result_item_ids=[])]

    assert ("error", "constructable_needs_result") in _recipe_codes(objects)


@pytest.mark.parametrize(
    ("result_ids", "code"),
    [
        (["GHOST"], "constructable_result_missing"),
        (["BATTERY"], "constructable_result_is_ingredient"),
        (["LANTERN_RECIPE"], "constructable_result_is_recipe"),
    ],
)
async def test_recipe_rejects_bad_results(result_ids, code):
    objects = [*_ingredients_and_result(), _recipe(result_item_ids=result_ids)]

    assert ("error", code) in _recipe_codes(objects)


async def test_recipe_warns_on_visible_result_and_foreign_kept_ingredient():
    objects = [*_ingredients_and_result(hidden=False), _recipe(kept_ingredients=["ROPE"])]

    codes = _recipe_codes(objects)

    assert ("warn", "constructable_result_not_hidden") in codes
    assert ("warn", "constructable_kept_not_ingredient") in codes


async def test_recipe_results_start_hidden_on_import():
    # Arrange: the manifest forgot to hide the result.
    objects = [*_ingredients_and_result(hidden=False), _recipe(is_hidden=False)]

    # Act
    results = recipe_result_ids(objects)

    # Assert: recipe and result start hidden, ingredients keep their flag.
    assert results == {"LANTERN"}
    hidden = {o["id"]: starts_hidden(o, results) for o in objects}
    assert hidden == {"BATTERY": False, "TORCH": False, "LANTERN": True, "LANTERN_RECIPE": True}


async def test_recipe_never_visible_in_session_merge():
    # Arrange: even a session override cannot reveal a recipe.
    ent = {"id": "LANTERN_RECIPE", "item_type": "CONSTRUCTABLE", "is_hidden": True}

    # Act
    merged = _merge_session_entity(ent, {"LANTERN_RECIPE": {"is_hidden": False}}, {})

    # Assert
    assert merged["is_hidden"] is True


# ---------------------------------------------------------------------------
# Engine deterministic resolution
# ---------------------------------------------------------------------------


def _entity(eid: str, name: str, **fields) -> WorldEntity:
    defaults = {
        "session_id": "session-1",
        "entity_type": "OBJECT",
        "item_type": "DEFAULT",
        "description": f"A {name.lower()}.",
        "current_scene_id": "START",
        "is_hidden": False,
        "is_in_inventory": False,
    }
    return WorldEntity(id=eid, name=name, **{**defaults, **fields})


def _recipe_entity(results=("LANTERN",), kept=(), ingredients=("BATTERY", "TORCH")):
    return _entity(
        "LANTERN_RECIPE",
        "Lantern recipe",
        item_type="CONSTRUCTABLE",
        is_hidden=True,
        combination_ingredients=list(ingredients),
        metadata_json={"result_item_ids": list(results), "kept_ingredients": list(kept)},
    )


async def _seed(db, entities: list[WorldEntity], inventory: list[str]):
    user = User(username="player1", hashed_password="pw", role="user")
    adv = AdventureTemplate(
        id="adv-1", title="Test", owner_id="admin", time_per_turn=5, strict_rules=True
    )
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
        inventory=[{"id": i, "name": i.title()} for i in inventory],
    )
    db.add(avatar)
    await db.flush()
    db.add(
        SessionState(
            session_id="session-1",
            template_id=adv.id,
            avatar_id=avatar.id,
            user_id=user.id,
            current_scene_id="START",
            in_game_time=0,
        )
    )
    db.add_all(entities)
    await db.commit()
    manager = GameTurnManager(db, "session-1", user)
    await manager.initialize()
    return manager


def _carried(*ids: str) -> list[WorldEntity]:
    return [_entity(i, i.title(), is_in_inventory=True) for i in ids]


def _lantern(**fields) -> WorldEntity:
    return _entity("LANTERN", "Lantern", **{"is_hidden": True, **fields})


def _update(event: GameEvent, eid: str):
    return next((u for u in event.updated_entities or [] if u.entity_id == eid), None)


async def test_recipe_reveals_result_when_all_ingredients_combined(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        # Arrange: the result is a SWITCH, not the recipe itself.
        entities = [*_carried("BATTERY", "TORCH"), _lantern(item_type="SWITCH"), _recipe_entity()]
        manager = await _seed(db, entities, ["BATTERY", "TORCH"])
        event = GameEvent(combination_intent=True)

        # Act
        messages = await manager._enforce_constructable_combination(
            event, "combine battery with torch"
        )

        # Assert: ingredients consumed, result revealed into the inventory, recipe untouched.
        assert any("Lantern" in m for m in messages)
        assert set(event.removed_inventory_item_ids or []) == {"BATTERY", "TORCH"}
        assert _update(event, "LANTERN").is_hidden is False
        assert [i.id for i in event.new_inventory_items or []] == ["LANTERN"]
        assert event.new_inventory_items[0].item_type == "SWITCH"
        assert _update(event, "LANTERN_RECIPE") is None
        assert not any(m.entity_id == "LANTERN" for m in event.moved_entities or [])


async def test_recipe_keeps_kept_ingredients_and_reveals_all_results(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        # Arrange: the torch is a tool that survives; the recipe yields two items.
        entities = [
            *_carried("BATTERY", "TORCH"),
            _lantern(),
            _entity("MANUAL", "Manual", item_type="READABLE", is_hidden=True),
            _recipe_entity(results=("LANTERN", "MANUAL"), kept=("TORCH",)),
        ]
        manager = await _seed(db, entities, ["BATTERY", "TORCH"])
        event = GameEvent(combination_intent=True)

        # Act
        await manager._enforce_constructable_combination(event, "combine battery with torch")

        # Assert
        assert event.removed_inventory_item_ids == ["BATTERY"]
        assert {i.id for i in event.new_inventory_items or []} == {"LANTERN", "MANUAL"}


async def test_recipe_noop_when_ingredient_missing(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        # Arrange: the torch lies in another scene.
        entities = [
            *_carried("BATTERY"),
            _entity("TORCH", "Torch", current_scene_id="ELSEWHERE"),
            _lantern(),
            _recipe_entity(),
        ]
        manager = await _seed(db, entities, ["BATTERY"])
        event = GameEvent(combination_intent=True)

        # Act
        messages = await manager._enforce_constructable_combination(
            event, "combine battery with torch"
        )

        # Assert
        assert messages == []
        assert not event.removed_inventory_item_ids
        assert not event.updated_entities


async def test_recipe_noop_when_result_already_revealed(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        # Arrange: the result was revealed another way already.
        entities = [*_carried("BATTERY", "TORCH"), _lantern(is_hidden=False), _recipe_entity()]
        manager = await _seed(db, entities, ["BATTERY", "TORCH"])
        event = GameEvent(combination_intent=True)

        # Act
        messages = await manager._enforce_constructable_combination(
            event, "combine battery with torch"
        )

        # Assert: nothing to craft, nothing consumed.
        assert messages == []
        assert not event.removed_inventory_item_ids


async def test_recipe_noop_without_combine_intent(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        # Arrange
        entities = [*_carried("BATTERY", "TORCH"), _lantern(), _recipe_entity()]
        manager = await _seed(db, entities, ["BATTERY", "TORCH"])
        event = GameEvent()

        # Act: unrelated action, although all ingredients are carried.
        messages = await manager._enforce_constructable_combination(event, "look around the room")

        # Assert
        assert messages == []
        assert not event.removed_inventory_item_ids


async def test_recipe_consumes_scene_ingredient_and_places_result_in_scene(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        # Arrange: one ingredient carried, one visible in the scene; the result starts elsewhere.
        entities = [
            *_carried("BATTERY"),
            _entity("TORCH", "Torch"),
            _lantern(current_scene_id="WORKSHOP"),
            _recipe_entity(),
        ]
        manager = await _seed(db, entities, ["BATTERY"])
        event = GameEvent(combination_intent=True)

        # Act
        await manager._enforce_constructable_combination(event, "use battery on torch")

        # Assert
        assert event.removed_inventory_item_ids == ["BATTERY"]
        assert _update(event, "TORCH").is_hidden is True
        assert _update(event, "LANTERN").is_hidden is False
        move = next(m for m in event.moved_entities if m.entity_id == "LANTERN")
        assert move.to_scene_id == "START"
        assert not event.new_inventory_items


async def test_recipe_reverts_illegal_spawn_of_craft_only_result(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        # Arrange
        entities = [*_carried("BATTERY", "TORCH"), _lantern(), _recipe_entity()]
        manager = await _seed(db, entities, ["BATTERY", "TORCH"])
        event = GameEvent(
            new_inventory_items=[
                InventoryItem(id="LANTERN", name="Lantern"),
                InventoryItem(id="LANTERN_RECIPE", name="Lantern recipe"),
            ],
            updated_entities=[WorldEntityUpdate(entity_id="LANTERN", is_hidden=False)],
        )

        # Act
        messages = await manager._enforce_constructable_combination(event, "look at lantern")

        # Assert: neither the result nor the recipe enters the world.
        assert not event.new_inventory_items
        assert not event.updated_entities
        assert any("Rule Violation" in m for m in messages)


async def test_recipe_result_with_own_reveal_rule_may_appear_otherwise(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        # Arrange: the lantern can also be found under the bed.
        entities = [
            *_carried("BATTERY", "TORCH"),
            _lantern(reveal_rule="Player searches under the bed"),
            _recipe_entity(),
        ]
        manager = await _seed(db, entities, ["BATTERY", "TORCH"])
        event = GameEvent(
            updated_entities=[WorldEntityUpdate(entity_id="LANTERN", is_hidden=False)]
        )

        # Act
        messages = await manager._enforce_constructable_combination(event, "search under the bed")

        # Assert: the GM reveal stands.
        assert messages == []
        assert _update(event, "LANTERN").is_hidden is False


async def test_recipe_crafts_in_any_language_when_gm_flags_intent(setup_test_db):
    """No keyword lists: a French adventure crafts as soon as the GM flags combination_intent."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        # Arrange
        entities = [
            *_carried("PILE", "TORCHE"),
            _entity("LANTERNE", "Lanterne", is_hidden=True),
            _recipe_entity(results=("LANTERNE",), ingredients=("PILE", "TORCHE")),
        ]
        manager = await _seed(db, entities, ["PILE", "TORCHE"])

        # Act
        not_flagged = await manager._enforce_constructable_combination(
            GameEvent(combination_intent=False), "j'assemble la pile avec la torche"
        )
        crafted = await manager._enforce_constructable_combination(
            GameEvent(combination_intent=True), "j'assemble la pile avec la torche"
        )

        # Assert
        assert any("Lanterne" in m for m in crafted)
        assert not any("Lanterne" in m for m in not_flagged)
