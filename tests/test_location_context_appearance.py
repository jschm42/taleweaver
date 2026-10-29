from types import SimpleNamespace

from backend.engine.interaction.location_context import _describe_npc, build_world_npcs_context


def _npc(**overrides):
    values = {
        "id": "GUARD",
        "name": "Guard",
        "entity_type": "NPC",
        "description": "A bored guard.",
        "appearance": "burly, chainmail, red cape",
        "current_scene_id": "GATE",
        "spatial_position": None,
        "goal": None,
        "character": None,
        "hp": None,
        "max_hp": None,
        "mana": None,
        "max_mana": None,
        "stamina": None,
        "max_stamina": None,
        "inventory": [],
        "notes": None,
        "is_hidden": False,
        "moveable": False,
        "movement_type": "STATIONARY",
        "allowed_scenes": [],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_scene_npc_description_includes_looks_in_concise_mode():
    # Act
    line = _describe_npc(_npc(), "concise")

    # Assert
    assert "[Looks: burly, chainmail, red cape]" in line


def test_world_npcs_context_includes_looks():
    # Act
    context = build_world_npcs_context([_npc()], {"GATE": "City Gate"})

    # Assert
    assert "Location: City Gate, Looks: burly, chainmail, red cape" in context


def test_npc_without_appearance_has_no_looks_tag():
    # Act
    line = _describe_npc(_npc(appearance=None), "full")

    # Assert
    assert "Looks" not in line
