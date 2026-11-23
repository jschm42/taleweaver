"""Author-placed NPCs and items of a dynamic zone (``in: ZONE_ID``): blueprint to runtime.

Blueprint: engine/blueprint/zone_entities.py. Runtime: engine/world/dynamic_required_entities.py.
"""

from backend.engine.blueprint import analyze_blueprint, apply_blueprint, prepare_blueprint
from backend.engine.blueprint.prompt import blueprint_payload
from backend.engine.world.dynamic_required_entities import (
    merge_required_entities,
    npcs_to_persist,
    objects_to_persist,
    required_blocks,
    required_entities_summary,
)
from backend.engine.world.dynamic_scene_fallback import finalize_fallback_scene
from backend.engine.world.dynamic_scene_plan import apply_scene_plan_to_payload, roll_scene_plan
from backend.engine.world.dynamic_scene_schemas import (
    DynamicGeneratedScenePayload,
    normalize_dynamic_zone,
)

BLUEPRINT = """A haunted mine.

[Scene: HALL] Mine Hall
The miners' hall.

[Exit: HALL -> IRON_MINES] Collapsed shaft
theme: Flooded dwarven iron mine
max_depth: 3

[NPC: FOREMAN] Ghost Foreman
in: IRON_MINES
depth: max
type: BEING
A pale shade who still counts the carts.

[Item: MINE_KEY] Rusty Lift Key
in: IRON_MINES
depth: 2
Opens the old ore lift.

[Item: LANTERN] Miner's Lantern
in: HALL
"""

ZONE_TEXT = """[NPC: FOREMAN] Ghost Foreman
depth: max
type: BEING
A pale shade.

[Item: MINE_KEY] Rusty Lift Key
depth: 2
Opens the old ore lift.

[Item: RATIONS] Hard Tack
A dry ration."""


def _zone(depth: int, **extra) -> dict:
    zone = normalize_dynamic_zone(
        {
            "zone_id": "iron_mines",
            "theme": "Flooded dwarven iron mine",
            "max_depth": 3,
            "depth": depth,
            "max_npcs": 1,
            "required_entities": ZONE_TEXT,
            **extra,
        }
    )
    assert zone is not None
    return zone


def _payload(**overrides) -> DynamicGeneratedScenePayload:
    data = {
        "name": "Ore Gallery",
        "description": "Dripping stone.",
        "npcs": [
            {"id": "RAT", "name": "Giant Rat", "npc_type": "ANIMAL", "description": "Hungry."},
        ],
        "objects": [
            {"id": f"ROCK_{i}", "name": f"Rock {i}", "description": "A rock."} for i in range(5)
        ],
    }
    data.update(overrides)
    return DynamicGeneratedScenePayload.model_validate(data)


# --- blueprint ---------------------------------------------------------------------------------


def test_zone_ids_are_valid_locations_and_depth_outside_a_zone_warns():
    # Act
    blueprint, missing = analyze_blueprint(BLUEPRINT + "\n[NPC: GUARD] Guard\nin: HALL\ndepth: 2\n")

    # Assert
    assert "IRON_MINES" not in missing
    assert not blueprint.errors
    assert any("depth: only applies" in w.message for w in blueprint.warnings)


def test_zone_entities_move_into_the_zone_and_reach_the_manifest():
    # Arrange
    prepared = prepare_blueprint(BLUEPRINT)
    assert prepared is not None
    manifest = {
        "scenes": [{"id": "HALL", "name": "Mine Hall", "description": "The miners' hall."}],
        "exits": [],
        "npcs": [],
        "objects": [],
    }

    # Act
    payload = blueprint_payload(prepared.blueprint)
    apply_blueprint(manifest, prepared.blueprint)

    # Assert: the world generator never creates them, it only learns their ids.
    kinds = {(b.kind, b.ref) for b in prepared.blueprint.blocks}
    assert ("npc", "FOREMAN") not in kinds and ("item", "MINE_KEY") not in kinds
    assert ("item", "LANTERN") in kinds
    exit_payload = payload["exits"][0]
    assert exit_payload["runtime_entities"] == ["FOREMAN", "MINE_KEY"]
    assert "dynamic_zone.required_entities" not in exit_payload.get("fixed", {})
    zone = manifest["exits"][0]["dynamic_zone"]
    assert "[NPC: FOREMAN] Ghost Foreman" in zone["required_entities"]
    assert "in: IRON_MINES" not in zone["required_entities"]
    assert "depth: max" in zone["required_entities"]
    assert normalize_dynamic_zone(zone)["required_entities"] == zone["required_entities"]


# --- runtime -----------------------------------------------------------------------------------


def test_entities_appear_at_their_depth_and_only_once_per_cluster():
    # Act
    first = [b.ref for b in required_blocks(_zone(1))]
    second = [b.ref for b in required_blocks(_zone(2))]
    deepest = [b.ref for b in required_blocks(_zone(3))]
    generated = [{"scene_id": "DYN_A", "npcs": [], "objects": [{"id": "MINE_KEY"}]}]
    second_again = [b.ref for b in required_blocks(_zone(2), generated)]

    # Assert: no depth = the first room generated (until it exists somewhere in the cluster).
    assert first == ["RATIONS"]
    assert second == ["MINE_KEY", "RATIONS"]
    assert deepest == ["FOREMAN", "RATIONS"]
    assert second_again == ["RATIONS"]


def test_required_entities_survive_every_cap():
    # Arrange: the room may hold 1 NPC and the LLM already filled 5 objects and the NPC slot.
    zone = _zone(3)
    plan = roll_scene_plan(zone, max_npcs=1)
    payload = _payload()

    # Act
    protected = apply_scene_plan_to_payload(payload, plan, zone, None)

    # Assert
    npc_ids = [n.id for n in npcs_to_persist(payload, 1)]
    object_ids = [o.id for o in objects_to_persist(payload)]
    assert {"FOREMAN", "RATIONS"} <= protected
    assert npc_ids[0] == "FOREMAN"
    assert "RATIONS" in object_ids
    assert plan["target_npcs"] >= 1 and plan["allow_items"] is True


def test_a_generated_entity_with_the_same_id_is_replaced_not_duplicated():
    # Arrange
    payload = _payload(objects=[{"id": "RATIONS", "name": "Old Bread", "description": "Stale."}])

    # Act
    merge_required_entities(payload, required_blocks(_zone(1)))

    # Assert
    assert [o.id for o in payload.objects] == ["RATIONS"]
    assert payload.objects[0].name == "Hard Tack"


def test_fallback_scenes_keep_the_required_entities():
    # Act
    fallback = finalize_fallback_scene("a shaft", _zone(3), None, None)

    # Assert
    assert "FOREMAN" in {n.id for n in fallback.npcs}


def test_the_cluster_planner_learns_where_the_entities_appear():
    # Act
    summary = required_entities_summary(_zone(1))

    # Assert
    assert "NPC FOREMAN (Ghost Foreman) in room depth 3" in summary
    assert "ITEM RATIONS (Hard Tack) in the first room" in summary


def test_a_placed_container_holds_the_placed_items_it_contains():
    # Arrange
    text = "[Container: ORE_CART] Ore Cart\ncontains: MINE_KEY\n\n[Item: MINE_KEY] Lift Key\n"
    zone = _zone(1, required_entities=text)
    payload = _payload(objects=[])

    # Act
    merge_required_entities(payload, required_blocks(zone))

    # Assert
    cart = next(o for o in payload.objects if o.id == "ORE_CART")
    assert cart.item_type == "CONTAINER" and cart.inventory == ["MINE_KEY"]
