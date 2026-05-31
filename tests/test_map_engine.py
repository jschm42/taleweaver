from types import SimpleNamespace

from backend.engine.map_engine import MapEngine


def test_augment_map_data_adds_return_edge_for_known_target_scene():
    map_dict = {
        "nodes": {
            "DINER_ENTRANCE": {"id": "DINER_ENTRANCE", "label": "Diner Entrance"},
            "DINER_INTERIOR": {"id": "DINER_INTERIOR", "label": "Diner Interior"},
        },
        "edges": [
            {"from": "DINER_ENTRANCE", "to": "DINER_INTERIOR", "label": "swing door", "is_locked": False}
        ],
        "current_scene_id": "DINER_INTERIOR",
    }

    exits = [
        SimpleNamespace(
            from_scene_id="DINER_INTERIOR",
            to_scene_id="DINER_ENTRANCE",
            label="back to entrance",
            is_locked=False,
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
        )
    ]

    augmented = MapEngine.augment_map_data(map_dict, exits, "DINER_ENTRANCE")

    assert "KITCHEN" in augmented["nodes"]
    assert augmented["nodes"]["KITCHEN"]["is_unknown"] is True
    assert any(
        edge["from"] == "DINER_ENTRANCE" and edge["to"] == "KITCHEN"
        for edge in augmented["edges"]
    )