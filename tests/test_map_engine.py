from types import SimpleNamespace

import pytest

from backend.engine.interaction.map_engine import MapEngine, load_map_exits
from backend.models.world_entity import WorldExit
from tests.conftest import TestSessionLocal
from tests.test_game_loop import _seed_game_context


def test_augment_map_data_adds_return_edge_for_known_target_scene():
    map_dict = {
        "nodes": {
            "DINER_ENTRANCE": {"id": "DINER_ENTRANCE", "label": "Diner Entrance"},
            "DINER_INTERIOR": {"id": "DINER_INTERIOR", "label": "Diner Interior"},
        },
        "edges": [
            {
                "from": "DINER_ENTRANCE",
                "to": "DINER_INTERIOR",
                "label": "swing door",
                "is_locked": False,
            }
        ],
        "current_scene_id": "DINER_INTERIOR",
    }

    exits = [
        SimpleNamespace(
            from_scene_id="DINER_INTERIOR",
            to_scene_id="DINER_ENTRANCE",
            label="back to entrance",
            is_locked=False,
            exit_type="directional",
        )
    ]

    augmented = MapEngine.augment_map_data(map_dict, exits, "DINER_INTERIOR")

    assert any(
        edge["from"] == "DINER_INTERIOR" and edge["to"] == "DINER_ENTRANCE"
        for edge in augmented["edges"]
    )


def test_augment_map_data_still_adds_placeholder_for_unknown_target_scene():
    map_dict = {
        "nodes": {
            "DINER_ENTRANCE": {"id": "DINER_ENTRANCE", "label": "Diner Entrance"},
        },
        "edges": [],
        "current_scene_id": "DINER_ENTRANCE",
    }

    exits = [
        SimpleNamespace(
            from_scene_id="DINER_ENTRANCE",
            to_scene_id="KITCHEN",
            label="kitchen door",
            is_locked=False,
            exit_type="directional",
        )
    ]

    augmented = MapEngine.augment_map_data(map_dict, exits, "DINER_ENTRANCE")

    assert "KITCHEN" in augmented["nodes"]
    assert augmented["nodes"]["KITCHEN"]["is_unknown"] is True
    assert any(
        edge["from"] == "DINER_ENTRANCE" and edge["to"] == "KITCHEN" for edge in augmented["edges"]
    )


def _door(**scope) -> WorldExit:
    return WorldExit(from_scene_id="START", to_scene_id="LOCKED_ROOM", label="door",
                     exit_type="bidirectional", item_to_unlock="RUSTY_KEY", **scope)  # fmt: skip


@pytest.mark.asyncio
async def test_load_map_exits_never_mixes_template_and_session_rows(setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange: the session copy is unlocked, the template original stays locked
        _user, _adv, _avatar, state = await _seed_game_context(db)
        db.add(_door(template_id=state.template_id, is_locked=True))
        db.add(_door(session_id=state.session_id, is_locked=False))
        await db.commit()

        # Act
        session_exits = await load_map_exits(db, state.template_id, state.session_id)
        template_exits = await load_map_exits(db, state.template_id, None)

        # Assert
        assert [ex.is_locked for ex in session_exits] == [False]
        assert [ex.is_locked for ex in template_exits] == [True]


def _exit(from_id: str, to_id: str, exit_type: str = "one_way") -> SimpleNamespace:
    return SimpleNamespace(
        id=f"{from_id}->{to_id}",
        from_scene_id=from_id,
        to_scene_id=to_id,
        label=f"{from_id} to {to_id}",
        is_locked=False,
        exit_type=exit_type,
        lock_description="",
        code_to_unlock="",
        item_to_unlock="",
        rule_to_unlock="",
    )


def _visited_map(*scene_ids: str, current: str) -> dict:
    return {
        "nodes": {sid: {"id": sid, "label": sid} for sid in scene_ids},
        "edges": [],
        "current_scene_id": current,
    }


def _pairs(map_dict: dict) -> set[tuple[str, str]]:
    return {(edge["from"], edge["to"]) for edge in map_dict["edges"]}


def test_augment_map_data_adds_exits_between_visited_scenes():
    # Arrange
    map_dict = _visited_map("HEARTH", "TENTS", "HOLLOW", current="TENTS")
    exits = [
        _exit("HEARTH", "HOLLOW", "bidirectional"),
        _exit("HEARTH", "TENTS", "bidirectional"),
        _exit("HOLLOW", "RIVER", "bidirectional"),
    ]

    # Act
    augmented = MapEngine.augment_map_data(map_dict, exits, "TENTS")

    # Assert
    assert _pairs(augmented) == {("HEARTH", "HOLLOW"), ("HEARTH", "TENTS")}
    assert "RIVER" not in augmented["nodes"]


def test_augment_map_data_does_not_duplicate_a_recorded_two_way_exit():
    # Arrange
    map_dict = _visited_map("HEARTH", "HOLLOW", current="HOLLOW")
    map_dict["edges"].append(
        {"from": "HOLLOW", "to": "HEARTH", "label": "", "exit_type": "bidirectional"}
    )
    exits = [_exit("HEARTH", "HOLLOW", "bidirectional")]

    # Act
    augmented = MapEngine.augment_map_data(map_dict, exits, "HOLLOW")

    # Assert
    assert len(augmented["edges"]) == 1


def test_augment_map_data_keeps_one_way_exits_in_both_directions():
    # Arrange
    map_dict = _visited_map("CLIFF", "BEACH", "CAVE", current="CAVE")
    exits = [_exit("CLIFF", "BEACH"), _exit("BEACH", "CLIFF")]

    # Act
    augmented = MapEngine.augment_map_data(map_dict, exits, "CAVE")

    # Assert
    assert _pairs(augmented) == {("CLIFF", "BEACH"), ("BEACH", "CLIFF")}
