"""npc.consume(): an NPC uses a carried consumable; its HP / Mana / Stamina effects apply."""

from typing import Any

from backend.engine.scripting.context import GameContext
from backend.engine.scripting.item_ops import DESTROYED_SCENE_ID
from backend.engine.scripting.runner import ScriptRunner


def _context(**npc_fields: Any) -> GameContext:
    npc = {
        "id": "BRAM",
        "name": "Bram",
        "entity_type": "NPC",
        "current_scene_id": "TAVERN",
        "hp": 40,
        "max_hp": 50,
        "mana": 5,
        "max_mana": 20,
        "stamina": 10,
        "max_stamina": 30,
        "inventory": [{"id": "POTION", "name": "Potion"}, {"id": "ROCK", "name": "Rock"}],
        **npc_fields,
    }
    return GameContext(
        avatar_data={"name": "Hero"},
        current_scene_id="TAVERN",
        entities={
            "BRAM": npc,
            "POTION": {
                "id": "POTION",
                "name": "Potion",
                "entity_type": "OBJECT",
                "item_type": "CONSUMABLE",
                "current_scene_id": "INVENTORY",
                "metadata_json": {"hp_change": 25, "mana_change": 8, "stamina_change": -4},
            },
            "POISON": {
                "id": "POISON",
                "name": "Poison",
                "entity_type": "OBJECT",
                "item_type": "CONSUMABLE",
                "current_scene_id": "INVENTORY",
                "description": "Drains 60 HP.",
            },
            "ROCK": {
                "id": "ROCK",
                "name": "Rock",
                "entity_type": "OBJECT",
                "item_type": "DEFAULT",
                "current_scene_id": "INVENTORY",
            },
        },
    )


def _run(ctx: GameContext, code: str) -> dict[str, Any]:
    scope: dict[str, Any] = {"tw": ctx}
    ScriptRunner([]).execute_code(code, scope, script_id="test")
    return scope


def test_consume_applies_effects_capped_and_destroys_the_item():
    # Arrange
    ctx = _context()

    # Act
    scope = _run(ctx, "result = tw.npcs.consume('BRAM', 'POTION')")

    # Assert
    assert scope["result"] == {"hp": 25, "mana": 8, "stamina": -4}
    npc = ctx.npcs.get("BRAM")
    assert (npc.hp, npc.mana, npc.stamina) == (50, 13, 6)
    assert not npc.has_item("POTION")
    assert ctx.objects.location("POTION")["type"] == "destroyed"
    assert ctx.objects.get("POTION").current_scene_id == DESTROYED_SCENE_ID


def test_consume_returns_none_for_items_the_npc_lacks_or_non_consumables():
    # Arrange
    ctx = _context()

    # Act
    scope = _run(
        ctx,
        "missing = tw.npcs.get('BRAM').consume('POISON')\n"
        "rock = tw.npcs.get('BRAM').consume('ROCK')",
    )

    # Assert
    assert scope["missing"] is None
    assert scope["rock"] is None
    assert ctx.npcs.get("BRAM").has_item("ROCK")
    assert ctx.npcs.get("BRAM").hp == 40


def test_consuming_a_deadly_item_defeats_the_npc():
    # Arrange
    ctx = _context(inventory=[{"id": "POISON", "name": "Poison"}])

    # Act
    _run(ctx, "tw.npcs.get('BRAM').consume('POISON')")

    # Assert
    npc = ctx.npcs.get("BRAM")
    assert npc.hp == 0
    assert npc.is_defeated is True


def test_heal_is_capped_and_damage_reduces_hp():
    # Arrange
    ctx = _context()

    # Act
    _run(ctx, "npc = tw.npcs.get('BRAM')\nnpc.heal(30)\nnpc.damage(15)")

    # Assert
    assert ctx.npcs.get("BRAM").hp == 35
