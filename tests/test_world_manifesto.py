
from backend.engine import world_generator


def test_world_manifesto_parsing_and_dump():
    """Verify that a minimal WorldManifesto with a protagonist validates and round-trips to dict."""
    manifest = {
        "protagonist": {
            "name": "Ari Ember",
            "role": "Royal Chef",
            "description": "A pragmatic, quick-thinking chef who once served the palace kitchens.",
            "goal": "Reclaim the kitchen.",
            "character": "Stubborn but creative.",
            "strength": 10,
            "dexterity": 12,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10,
            "armor_class": 10,
            "hp": 100,
            "mana": 100,
            "stamina": 100,
            "starting_inventory": [],
            "starting_equipment": {
                "Head": "", "Chest": "", "Hands": "", "Legs": "", "Feet": "",
                "Neck": "", "Ring_1": "", "Ring_2": "", "MainHand": "", "OffHand": ""
            }
        },
        "teaser": "A culinary quest.",
        "language": "English",
        "origin_id": "",
        "plot": "Reclaim the kitchen from the goblin chef.",
        "rules": "",
        "intro_text": "",
        "walkthrough": "",
        "completed_condition": "",
        "gameover_condition": "",
        "tts_director_notes": "",
        "scenes": [
            {"id": "KITCHEN_01", "name": "Abandoned Kitchen", "description": "Dusty pots and a cold hearth."}
        ],
        "exits": [],
        "npcs": [],
        "objects": [],
        "quests": [],
        "awards": []
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
