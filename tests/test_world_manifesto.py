
from backend.engine import world_generator


def test_world_manifesto_parsing_and_dump():
    """Verify that a minimal WorldManifesto with a protagonist validates and round-trips to dict."""
    manifest = {
        "protagonist": {
            "name": "Ari Ember",
            "role": "Royal Chef",
            "description": "A pragmatic, quick-thinking chef who once served the palace kitchens."
        },
        "scenes": [
            {"id": "KITCHEN_01", "name": "Abandoned Kitchen", "description": "Dusty pots and a cold hearth."}
        ],
        "exits": [],
        "npcs": [],
        "objects": [],
        "quests": []
    }

    WM = world_generator.WorldManifesto

    # Support both pydantic v2 (.model_validate) and v1 (.parse_obj)
    try:
        manifesto = WM.model_validate(manifest)
    except AttributeError:
        manifesto = WM.parse_obj(manifest)

    assert manifesto.protagonist.name == "Ari Ember"
    assert manifesto.protagonist.role == "Royal Chef"
    assert len(manifesto.scenes) == 1

    # Ensure we can dump back to a dict (v2: model_dump, v1: dict)
    try:
        dumped = manifesto.model_dump()
    except AttributeError:
        dumped = manifesto.dict()

    assert "protagonist" in dumped
    assert dumped["protagonist"]["role"] == "Royal Chef"
