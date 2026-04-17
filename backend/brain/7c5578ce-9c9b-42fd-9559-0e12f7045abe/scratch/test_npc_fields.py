import pytest
from backend.engine import world_generator

def test_world_manifesto_npc_fields():
    """Verify that new NPC fields (type, movement, stats) validate correctly."""
    manifest = {
        "protagonist": {
            "name": "Ari Ember",
            "role": "Royal Chef",
            "description": "..."
        },
        "scenes": [
            {"id": "KITCHEN_01", "name": "Kitchen", "description": "..."}
        ],
        "exits": [],
        "npcs": [
            {
                "id": "GUARD_01",
                "type": "NPC",
                "name": "City Guard",
                "description": "A stoic sentinel.",
                "start_scene_id": "KITCHEN_01",
                "spatial_position": "by the door",
                "npc_type": "HUMANOID",
                "movement_type": "STATIONARY",
                "hp": 50,
                "mana": 10,
                "stamina": 100,
                "is_hidden": False
            }
        ],
        "objects": []
    }

    WM = world_generator.WorldManifesto
    manifesto = WM.model_validate(manifest)

    npc = manifesto.npcs[0]
    assert npc.npc_type == "HUMANOID"
    assert npc.movement_type == "STATIONARY"
    assert npc.hp == 50
    assert npc.mana == 10
    assert npc.stamina == 100
