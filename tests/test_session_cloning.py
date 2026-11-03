"""Session copies of template entities keep everything the game reads from the session row."""

from backend.api.routes.adventures.session_cloning import clone_entity
from backend.models.world_entity import WorldEntity


def _template_npc() -> WorldEntity:
    return WorldEntity(
        id="GARGOYLE",
        template_id="tmpl-1",
        entity_type="NPC",
        name="Grimsby",
        description="A stone bust.",
        appearance="grey stone, curled horns",
        voice="voice-123",
        goal="Mock apprentices",
        character="Sarcastic",
        reveal_rule="after the lever is pulled",
        current_scene_id="LAB",
        inventory=["RING"],
        metadata_json={"attack_mode": "PASSIVE"},
    )


def test_clone_keeps_voice_persona_and_reveal_rule():
    # Arrange
    template = _template_npc()

    # Act
    copy = clone_entity(template, "session-1", None)

    # Assert
    assert (copy.session_id, copy.template_id) == ("session-1", None)
    assert copy.voice == "voice-123"
    assert (copy.goal, copy.character) == ("Mock apprentices", "Sarcastic")
    assert copy.appearance == "grey stone, curled horns"
    assert copy.reveal_rule == "after the lever is pulled"


def test_clone_does_not_share_mutable_fields_with_the_template():
    # Arrange
    template = _template_npc()

    # Act
    copy = clone_entity(template, "session-1", None)
    copy.inventory.append("COIN")
    copy.metadata_json["attack_mode"] = "ATTACK_ON_SIGHT"

    # Assert
    assert template.inventory == ["RING"]
    assert template.metadata_json == {"attack_mode": "PASSIVE"}
