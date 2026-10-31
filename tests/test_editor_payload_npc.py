"""The editor payload carries an NPC's trigger scripts, so saving the NPC does not wipe them."""

from backend.api.routes.adventures.editing.payload import _serialize_model
from backend.models.world_entity import WorldEntity


def test_npc_trigger_scripts_are_flat_in_the_editor_payload():
    # Arrange
    npc = WorldEntity(
        id="GARGOYLE",
        template_id="tmpl-1",
        entity_type="NPC",
        name="Grimsby",
        description="A stone bust.",
        hp=200,
        metadata_json={
            "attack_mode": "PASSIVE",
            "on_interact_script": "tw.dialog.tree(TALK)",
            "on_defeat_text": "The stone cracks.",
        },
    )

    # Act
    payload = _serialize_model(npc)

    # Assert
    assert payload["on_interact_script"] == "tw.dialog.tree(TALK)"
    assert payload["on_defeat_text"] == "The stone cracks."
    assert payload["on_protagonist_enters_scene_script"] == ""
    assert payload["metadata_json"]["attack_mode"] == "PASSIVE"
