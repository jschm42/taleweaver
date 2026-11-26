"""World schemas tolerate empty hallucinated keys but still reject unknown keys with content."""

import pytest
from pydantic import ValidationError

from backend.engine.world.world_schemas import WorldObjectSchema


def _object_payload(**extra) -> dict:
    return {
        "id": "SW_NEON_SIGN",
        "name": "Neon Sign",
        "description": "A flickering sign above the diner door.",
        "start_scene_id": "DINER",
        "spatial_position": "above the door",
        "item_type": "SWITCH",
        "is_hidden": False,
        "is_portable": False,
        **extra,
    }


@pytest.mark.parametrize("empty_value", [None, "", [], {}])
def test_object_drops_empty_unknown_key(empty_value) -> None:
    # Arrange
    payload = _object_payload(on_success_script_text=empty_value)

    # Act
    obj = WorldObjectSchema(**payload)

    # Assert
    assert obj.id == "SW_NEON_SIGN"
    assert "on_success_script_text" not in obj.model_dump()


def test_object_rejects_unknown_key_with_content() -> None:
    # Arrange
    payload = _object_payload(on_success_script_text="The sign buzzes to life.")

    # Act / Assert
    with pytest.raises(ValidationError, match="on_success_script_text"):
        WorldObjectSchema(**payload)


def test_voice_assignment_field_is_declared() -> None:
    # Arrange: the voice assignment requirement asks for a `voice` field on every NPC and
    # the protagonist; under extra="forbid" an undeclared field fails the whole manifest.
    from backend.engine.world.world_prompt_builder import _build_voice_assignment_requirement
    from backend.engine.world.world_schemas import ProtagonistSchema, WorldNPCSchema

    # Act
    requirement = _build_voice_assignment_requirement(True)

    # Assert
    assert "`voice` field" in requirement or not requirement
    assert "voice" in WorldNPCSchema.model_fields
    assert "voice" in ProtagonistSchema.model_fields
