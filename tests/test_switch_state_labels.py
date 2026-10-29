"""SWITCH state IDs (script keys) and their optional in-game labels."""

import pytest

from backend.core.world_validator import validate_adventure
from backend.engine.blueprint import analyze_blueprint
from backend.engine.interaction.location_context import _switch_details
from backend.engine.interaction.switch_states import (
    is_valid_state_id,
    normalize_state_id,
    normalize_state_labels,
    state_label,
)
from backend.engine.manifest_apply.objects import _switch_metadata
from backend.models.world_entity import WorldEntity
from tests.test_switch_validation import _auth_headers, _seed_template


@pytest.mark.parametrize(
    ("state", "valid"),
    [
        ("OFF", True),
        ("HALF-OPEN", True),
        ("LEVEL_2", True),
        ("ABCDEFGHIJKLMNO", True),  # 15 characters
        ("ABCDEFGHIJKLMNOP", False),  # 16 characters
        ("HALF OPEN", False),
        ("", False),
        ("off", False),  # IDs are stored upper-case
    ],
)
def test_state_id_rules(state, valid):
    assert is_valid_state_id(state) is valid


def test_normalize_state_id_keeps_dash_and_underscore():
    assert normalize_state_id(" half-open ") == "HALF-OPEN"
    assert normalize_state_id("level 2!") == "LEVEL_2"
    assert len(normalize_state_id("A" * 30)) == 15


def test_labels_accept_dict_or_list_and_fall_back_to_id():
    # Arrange
    states = ["OFF", "HALF-OPEN", "ON"]

    # Act
    from_dict = normalize_state_labels(states, {"off": "Dark", "ON": "  ", "GHOST": "x"})
    from_list = normalize_state_labels(states, [{"state": "HALF-OPEN", "label": "Half open"}])
    config = {"state_labels": {**from_dict, **from_list}}

    # Assert
    assert from_dict == {"OFF": "Dark"}
    assert state_label(config, "half-open") == "Half open"
    assert state_label(config, "ON") == "ON"


def test_manifest_switch_keeps_labels_and_cuts_long_ones():
    # Arrange
    obj = {
        "switch_states": ["off", "half-open"],
        "switch_state_labels": {"HALF-OPEN": "A label that is far too long"},
    }
    metadata: dict = {}

    # Act
    _switch_metadata(obj, metadata)

    # Assert
    switch = metadata["switch"]
    assert switch["states"] == ["OFF", "HALF-OPEN"]
    assert switch["state_labels"] == {"HALF-OPEN": "A label that is far"}
    assert switch["initial_state"] == "OFF"


def test_gm_context_shows_id_and_label():
    entity = WorldEntity(
        id="LEVER",
        item_type="SWITCH",
        metadata_json={
            "switch": {
                "states": ["OFF", "ON"],
                "state_labels": {"ON": "Lights on"},
                "initial_state": "ON",
            }
        },
    )

    details = _switch_details(entity, "full")

    assert 'ON "Lights on"' in details
    assert "OFF" in details


def test_blueprint_states_with_labels():
    # Arrange
    text = "Premise.\n\n[Switch: LEVER] Lever\nstates: OFF=Dark, half-open, ON=Lights on\n"

    # Act
    blueprint, _missing = analyze_blueprint(text)

    # Assert
    fixed = blueprint.first("item").fixed()
    assert blueprint.errors == []
    assert fixed["item_type"] == "SWITCH"
    assert fixed["switch_states"] == ["OFF", "HALF-OPEN", "ON"]
    assert fixed["switch_state_labels"] == {"OFF": "Dark", "ON": "Lights on"}


@pytest.mark.parametrize(
    "states",
    ["OFF, ABCDEFGHIJKLMNOP", "OFF, ON=This label is way too long"],
)
def test_blueprint_rejects_bad_state_ids_and_labels(states):
    blueprint, _missing = analyze_blueprint(
        f"Premise.\n\n[Switch: LEVER] Lever\nstates: {states}\n"
    )

    assert blueprint.errors


def test_validator_flags_bad_ids_and_long_labels():
    payload = {
        "adventure": {"id": "adv", "start_scene_id": "START", "title": "T", "teaser": "x"},
        "scenes": [{"id": "START", "label": "Start", "description": "A room."}],
        "npcs": [],
        "exits": [],
        "objects": [
            {
                "id": "LEVER",
                "entity_type": "OBJECT",
                "item_type": "SWITCH",
                "name": "Lever",
                "switch_states": ["OFF", "WAY_TOO_LONG_STATE_ID"],
                "switch_initial_state": "OFF",
                "switch_state_labels": {"OFF": "A label longer than twenty"},
            }
        ],
    }

    codes = {f.code for f in validate_adventure(payload)}

    assert "switch_invalid_state_id" in codes
    assert "switch_state_label_too_long" in codes


@pytest.mark.asyncio
async def test_editor_saves_labels_and_rejects_invalid_ids(client, setup_test_db):
    _user_id, tpl_id = await _seed_template("switch_labeler")
    headers = _auth_headers("switch_labeler")

    def body(states, labels):
        return {
            "entity_id": "LABEL_SWITCH",
            "scene_id": "SCENE_X",
            "entity_type": "OBJECT",
            "item_type": "SWITCH",
            "name": "Switch",
            "description": "A switch.",
            "metadata_json": {
                "switch": {"states": states, "initial_state": states[0], "state_labels": labels}
            },
        }

    url = f"/api/adventures/{tpl_id}/editor/entity"
    bad_id = await client.post(url, headers=headers, json=body(["OFF", "HALF OPEN"], {}))
    long_label = await client.post(url, headers=headers, json=body(["OFF", "ON"], {"ON": "x" * 21}))
    ok = await client.post(
        url, headers=headers, json=body(["OFF", "HALF-OPEN"], {"HALF-OPEN": "Half open", "OFF": ""})
    )

    assert bad_id.status_code == 400
    assert "Invalid switch state ID" in bad_id.text
    assert long_label.status_code == 400
    assert ok.status_code == 200, ok.text
    switch = ok.json()["entity"]["metadata_json"]["switch"]
    assert switch["states"] == ["OFF", "HALF-OPEN"]
    assert switch["state_labels"] == {"HALF-OPEN": "Half open"}
