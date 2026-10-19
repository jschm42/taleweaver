"""The AI-fix context must resolve the validator's generic ``entity:<ID>`` locations."""

from backend.api.routes.adventures.editor import _format_focused_world_block


def test_ai_fix_context_resolves_generic_entity_location():
    summary = {
        "adventure": {"title": "T"},
        "scenes": [{"id": "START"}],
        "npcs": [{"id": "TROLL", "name": "Troll"}],
        "objects": [{"id": "CHEST", "name": "Chest"}],
        "exits": [],
    }

    npc_block = _format_focused_world_block(summary, location="entity:TROLL")
    object_block = _format_focused_world_block(summary, location="entity:CHEST")

    assert "TARGET NPC (TROLL)" in npc_block
    assert "TARGET OBJECT (CHEST)" in object_block
