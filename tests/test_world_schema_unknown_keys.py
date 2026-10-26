"""World schemas tolerate empty hallucinated keys but still reject unknown keys with content."""

import pytest
from pydantic import ValidationError

from backend.engine.world_schemas import WorldObjectSchema


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
