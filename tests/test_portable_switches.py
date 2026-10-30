"""Portable switches (e.g. a TV remote): carried like items, still flippable from the inventory."""

from types import SimpleNamespace

import pytest

from backend.api.routes.adventures.sheet_snapshot import _with_switch_state
from backend.api.routes.adventures.turn_interactions import TurnInteractionsManager
from backend.engine.manifest_apply.objects import is_portable_default


@pytest.mark.parametrize(
    ("obj", "expected"),
    [
        ({"item_type": "SWITCH"}, False),
        ({"item_type": "static"}, False),
        ({"item_type": "PICKABLE"}, True),
        ({}, True),
        ({"item_type": "SWITCH", "is_portable": True}, True),
        ({"item_type": "PICKABLE", "is_portable": False}, False),
    ],
)
def test_is_portable_default(obj, expected):
    # Act / Assert
    assert is_portable_default(obj) is expected


def _switch(scene="TV_ROOM", hidden=False, in_inventory=False):
    return SimpleNamespace(
        id="REMOTE", current_scene_id=scene, is_hidden=hidden, is_in_inventory=in_inventory
    )


def _in_reach(ent, states):
    manager = SimpleNamespace(state=SimpleNamespace(current_scene_id="TV_ROOM"))
    return TurnInteractionsManager._switch_in_reach(manager, ent, states)


def test_switch_in_current_scene_is_in_reach():
    # Arrange
    ent = _switch()

    # Act / Assert
    assert _in_reach(ent, {}) is True


def test_switch_in_other_scene_is_out_of_reach():
    # Arrange
    ent = _switch(scene="HALL")

    # Act / Assert
    assert _in_reach(ent, {}) is False


def test_carried_switch_is_in_reach_anywhere():
    # Arrange
    ent = _switch(scene="HALL")
    states = {"REMOTE": {"is_in_inventory": True, "current_scene_id": "INVENTORY"}}

    # Act / Assert
    assert _in_reach(ent, states) is True


def test_hidden_switch_is_out_of_reach():
    # Arrange
    ent = _switch()
    states = {"REMOTE": {"is_hidden": True}}

    # Act / Assert
    assert _in_reach(ent, states) is False


def test_inventory_item_gets_live_switch_state():
    # Arrange
    item = {"id": "REMOTE", "switch_state": "OFF"}

    # Act
    result = _with_switch_state(item, {"REMOTE": {"switch_state": "ON"}})

    # Assert
    assert result["switch_state"] == "ON"


def test_inventory_item_without_override_is_unchanged():
    # Arrange
    item = {"id": "KEY"}

    # Act
    result = _with_switch_state(item, {"OTHER": {"switch_state": "ON"}})

    # Assert
    assert "switch_state" not in result
