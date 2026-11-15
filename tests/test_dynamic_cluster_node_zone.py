"""Per-room zone overrides derived from a Dynamic Cluster Blueprint."""

from backend.engine.world.dynamic_cluster_blueprint import (
    DynamicClusterBlueprint,
    DynamicClusterNodeSpec,
    build_cluster_blueprint_prompt_section,
    build_fallback_cluster_blueprint,
    build_node_zone_context,
    normalize_cluster_blueprint,
)
from backend.engine.world.dynamic_cluster_node_zone import (
    apply_cluster_node_to_zone,
    restore_root_zone,
)
from backend.engine.world.dynamic_instructions_helper import resolve_active_instructions
from backend.engine.world.dynamic_scene_schemas import normalize_dynamic_zone

ROOT_THEME = "Dark stone dungeon beneath the village"
AUTHOR_TEXT = "Populate the dungeon with goblins and lootable chests."


def _zone(**extra):
    zone = normalize_dynamic_zone(
        {
            "zone_id": "dungeon",
            "theme": ROOT_THEME,
            "max_depth": 3,
            "instructions": AUTHOR_TEXT,
            "instructions_scope": "all_scenes",
            **extra,
        }
    )
    assert zone is not None
    return zone


def _cluster(zone):
    return normalize_cluster_blueprint(
        build_fallback_cluster_blueprint("Cellar Stairs", zone), zone, entry_scene_id="DYN_X_ABCD"
    )


def test_fallback_blueprint_gives_each_room_its_own_theme_and_instructions():
    # Arrange
    zone = _zone()

    # Act
    cluster = _cluster(zone)

    # Assert
    nodes = cluster["nodes"]
    assert len({n["theme_hint"] for n in nodes}) == len(nodes)
    assert len({n["generation_instructions"] for n in nodes}) == len(nodes)
    assert all(AUTHOR_TEXT in n["generation_instructions"] for n in nodes)
    assert cluster["antagonist"]


def test_author_scope_limits_fallback_room_instructions():
    # Arrange
    zone = _zone(instructions_scope="max_depth")

    # Act
    nodes = {n["node_id"]: n for n in _cluster(zone)["nodes"]}

    # Assert
    assert AUTHOR_TEXT in nodes["D3_1"]["generation_instructions"]
    assert "Cluster premise" not in nodes["D3_1"]["generation_instructions"]
    # Outside its scope the text still frames the story, but only as context.
    assert "Cluster premise (story context only" in nodes["D1_1"]["generation_instructions"]


def test_apply_node_replaces_loose_instructions_and_restore_brings_them_back():
    # Arrange
    zone = _zone(instructions_scope="once", depth=2)
    node_ctx = build_node_zone_context(_cluster(zone), "D2_1")

    # Act
    room = apply_cluster_node_to_zone(dict(zone), node_ctx)
    restored = restore_root_zone(room)

    # Assert
    assert room["theme"] == node_ctx["theme_hint"] != ROOT_THEME
    assert room["instructions"] == node_ctx["generation_instructions"]
    assert room["root_instructions"] == AUTHOR_TEXT
    assert resolve_active_instructions(room)[0] == node_ctx["generation_instructions"]
    assert restored["theme"] == ROOT_THEME
    assert restored["instructions"] == AUTHOR_TEXT
    assert restored["instructions_scope"] == "once"
    assert "instructions_source" not in restored


def test_reapplying_a_node_keeps_the_original_author_instructions():
    # Arrange
    zone = _zone()
    cluster = _cluster(zone)
    room = apply_cluster_node_to_zone(dict(zone), build_node_zone_context(cluster, "D1_1"))

    # Act
    again = apply_cluster_node_to_zone(dict(room), build_node_zone_context(cluster, "D2_2"))

    # Assert
    assert again["root_instructions"] == AUTHOR_TEXT
    assert again["root_instructions_scope"] == "all_scenes"


def test_room_overrides_survive_zone_normalization():
    # Arrange
    zone = _zone()
    room = apply_cluster_node_to_zone(dict(zone), build_node_zone_context(_cluster(zone), "D1_1"))

    # Act
    normalized = normalize_dynamic_zone(room)

    # Assert
    assert normalized is not None
    assert normalized["instructions_source"] == "cluster_blueprint"
    assert normalized["root_instructions"] == AUTHOR_TEXT


def test_blueprint_tag_instructions_stay_and_room_brief_goes_into_prompt():
    # Arrange
    tagged = "[Item: RUSTY_KEY] Rusty Key\ndepth: 2"
    zone = _zone(instructions=tagged)
    node_ctx = build_node_zone_context(_cluster(zone), "D2_1")

    # Act
    room = apply_cluster_node_to_zone(dict(zone), node_ctx)

    # Assert
    assert room["instructions"] == tagged
    assert "instructions_source" not in room
    assert "Room Generation Brief" in build_cluster_blueprint_prompt_section(room)


def test_llm_theme_copy_of_zone_theme_falls_back_to_room_hint():
    # Arrange
    zone = _zone()
    raw = DynamicClusterBlueprint(
        cluster_title="Goblin Warren",
        story_arc="Arc",
        climax_goal="Goal",
        nodes=[
            DynamicClusterNodeSpec(
                node_id="D1_1", label="Landing", theme_hint=ROOT_THEME, generation_instructions="X"
            )
        ],
    )

    # Act
    cluster = normalize_cluster_blueprint(raw, zone, entry_scene_id="DYN_X_ABCD")

    # Assert
    entry = cluster["nodes"][0]
    assert entry["theme_hint"] != ROOT_THEME
    assert entry["generation_instructions"] == "X"


def test_room_brief_keeps_rolled_counts_unless_author_scope_applies():
    # Arrange
    from backend.engine.world.dynamic_instructions_helper import adjust_plan_for_instructions

    rolled = {"target_npcs": 0, "npc_slots": [], "target_objects": 0, "allowed_item_types": []}
    once_zone = _zone(instructions_scope="once", depth=2)
    all_zone = _zone(instructions_scope="all_scenes", depth=2)
    brief_room = apply_cluster_node_to_zone(
        dict(once_zone), build_node_zone_context(_cluster(once_zone), "D2_1")
    )
    author_room = apply_cluster_node_to_zone(
        dict(all_zone), build_node_zone_context(_cluster(all_zone), "D2_1")
    )

    # Act
    brief_plan = adjust_plan_for_instructions(rolled, brief_room)
    author_plan = adjust_plan_for_instructions(rolled, author_room)

    # Assert
    assert brief_plan["has_instructions"] is True
    assert brief_plan["target_objects"] == 1
    assert brief_plan["target_npcs"] == 0
    assert author_plan["target_objects"] >= 3


def test_architect_prompt_builds_cluster_around_premise_for_any_scope():
    # Arrange
    from backend.engine.world.dynamic_cluster_architect import (
        _build_architect_system_prompt,
        _build_architect_user_prompt,
    )

    premise = (
        "Alex must fight through the dungeon to free Edgar from his cell. Goblins captured him."
    )
    zone = _zone(instructions=premise, instructions_scope="once")

    # Act
    user_prompt = _build_architect_user_prompt(
        adventure_title="T",
        adventure_setting="S",
        adventure_tone="Dark",
        origin_scene_name="Square",
        origin_scene_description="Village square",
        exit_label="Cellar Stairs",
        zone=zone,
    )
    system_prompt = _build_architect_system_prompt(zone, "English")

    # Assert
    assert f"CLUSTER PREMISE: {premise}" in user_prompt
    assert "story itself always spans the whole cluster" in system_prompt
