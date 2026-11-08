"""The World-Builder knows container-switches, take-locked items and dynamic sequences.

Covers the LLM generation schema, the generation prompts, the blueprint keys and the
manifest applier, so features the engine supports can also be generated.
"""

from backend.core.prompts import WORLD_GENERATION_SYSTEM_PROMPT
from backend.engine.blueprint import analyze_blueprint
from backend.engine.blueprint.prompt import blueprint_sequences
from backend.engine.manifest_apply.objects import item_numbers, object_metadata
from backend.engine.world.world_schemas import SequenceSchema, WorldObjectSchema
from backend.engine.world.world_scripting_prompt import build_scripts_requirement


def _microwave_payload() -> dict:
    return {
        "id": "MICROWAVE",
        "name": "Microwave",
        "description": "A dented office microwave.",
        "start_scene_id": "BREAK_ROOM",
        "spatial_position": "on the counter",
        "item_type": "CONTAINER_SWITCH",
        "is_hidden": False,
        "is_portable": False,
        "max_items": 1,
        "min_items": 1,
        "switch_states": ["OFF", "COOK"],
        "switch_initial_state": "OFF",
        "switch_disabled_states": ["COOK"],
        "switch_status_text": "Put something inside first.",
        "switch_outcomes": [
            {"on_state": "COOK", "effects": [{"type": "unlock_item", "target_id": "SODA_CAN"}]}
        ],
        "on_items_added_script": "tw.switch('MICROWAVE').enable_state('COOK')",
        "on_items_removed_script": "tw.switch('MICROWAVE').disable_state('COOK')",
    }


def test_object_schema_accepts_container_switch_fields() -> None:
    # Arrange
    payload = _microwave_payload()

    # Act
    obj = WorldObjectSchema(**payload).model_dump()

    # Assert
    assert obj["item_type"] == "CONTAINER_SWITCH"
    assert obj["max_items"] == 1
    assert obj["switch_disabled_states"] == ["COOK"]
    assert obj["switch_status_text"] == "Put something inside first."
    assert obj["on_items_removed_script"].startswith("tw.switch")
    assert obj["switch_outcomes"][0]["effects"][0]["type"] == "unlock_item"
    assert obj["locked"] is None


def test_object_schema_accepts_take_locked_item() -> None:
    # Arrange
    payload = {
        "id": "SODA_CAN",
        "name": "Soda Can",
        "description": "Stuck behind the glass.",
        "start_scene_id": "BREAK_ROOM",
        "spatial_position": "behind the glass",
        "item_type": "CONSUMABLE",
        "is_hidden": False,
        "is_portable": True,
        "locked": True,
    }

    # Act
    obj = WorldObjectSchema(**payload).model_dump()

    # Assert
    assert obj["locked"] is True


def test_applier_keeps_container_switch_metadata() -> None:
    # Arrange
    obj = WorldObjectSchema(**_microwave_payload()).model_dump()

    # Act
    metadata = object_metadata(obj, item_numbers(obj, {}))

    # Assert
    switch = metadata["switch"]
    assert switch["disabled_states"] == ["COOK"]
    assert switch["status_text"] == "Put something inside first."
    assert metadata["max_items"] == 1
    assert metadata["min_items"] == 1
    assert metadata["locked"] is False
    assert metadata["on_items_removed_script"].startswith("tw.switch")


def test_sequence_schema_keeps_activation_scene() -> None:
    # Arrange / Act
    seq = SequenceSchema(id="SEQ_ARCHIVE", order=2, title="Archive", activation_scene_id="ARCHIVE")

    # Assert
    assert seq.model_dump()["activation_scene_id"] == "ARCHIVE"


def test_generation_prompts_describe_new_features() -> None:
    # Arrange
    scripting = build_scripts_requirement(True)

    # Act / Assert
    for token in ("CONTAINER_SWITCH", "switch_disabled_states", "unlock_item", "min_items"):
        assert token in WORLD_GENERATION_SYSTEM_PROMPT
    assert "sequence_progression_mode" in WORLD_GENERATION_SYSTEM_PROMPT
    assert "activation_scene_id" in WORLD_GENERATION_SYSTEM_PROMPT
    for token in (
        "on_items_removed_script",
        "enable_state(id, *states)",
        "set_status_text",
        "tw.objects.lock(item_id)",
        "has_min_items",
        "tw.sequences (alias tw.sequence",
        "game_won",
    ):
        assert token in scripting


def test_blueprint_parses_progression_and_activation() -> None:
    # Arrange
    text = (
        "[World]\n"
        "progression: dynamic\n"
        "\n"
        "[Scene: HALL] Hall\n"
        "[Scene: ARCHIVE] Archive\n"
        "\n"
        "[Sequence: 1] The Hall\n"
        "goal_scene: ARCHIVE\n"
        "\n"
        "[Sequence: 2] The Archive\n"
        "activation: ARCHIVE\n"
    )

    # Act
    blueprint, missing = analyze_blueprint(text)

    # Assert
    assert blueprint.errors == []
    assert missing == []
    world = blueprint.of_kind("world")[0]
    assert world.fixed()["sequence_progression_mode"] == "dynamic"
    second = blueprint.of_kind("sequence")[1]
    assert second.fixed()["activation_scene_id"] == "ARCHIVE"
    assert blueprint_sequences(blueprint)[1]["activation_scene_id"] == "ARCHIVE"


def test_blueprint_reports_unknown_activation_scene() -> None:
    # Arrange
    text = "[Scene: HALL] Hall\n[Sequence: 1] Start\nactivation: NOWHERE\n"

    # Act
    _, missing = analyze_blueprint(text)

    # Assert
    assert "NOWHERE" in str(missing)
