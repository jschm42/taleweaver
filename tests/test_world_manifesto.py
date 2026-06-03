
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


def test_object_id_preprocessing():
    """Verify that WorldGenerator.preprocess_manifest_object_ids correctly prefixes references to object IDs in narrative texts."""
    manifest = {
        "protagonist": {
            "name": "Ari Ember",
            "role": "Chef",
            "description": "A chef carrying a golden_key in his pocket.",
            "goal": "Find the golden_key.",
            "character": "Searches for GOLDEN_KEY.",
            "strength": 10, "dexterity": 10, "intelligence": 10, "wisdom": 10, "charisma": 10, "armor_class": 10,
            "hp": 100, "mana": 100, "stamina": 100, "starting_inventory": [],
            "starting_equipment": {
                "Head": "", "Chest": "", "Hands": "", "Legs": "", "Feet": "",
                "Neck": "", "Ring_1": "", "Ring_2": "", "MainHand": "", "OffHand": ""
            }
        },
        "teaser": "Get the golden_key.",
        "language": "English",
        "origin_id": "",
        "plot": "The plot centers on the golden_key.",
        "rules": "",
        "intro_text": "You start with a golden_key.",
        "walkthrough": "Use the GOLDEN_KEY to unlock the exit.",
        "completed_condition": "Have golden_key.",
        "gameover_condition": "Lose the golden_key.",
        "tts_director_notes": "Emphasize the golden_key.",
        "scenes": [
            {
                "id": "KITCHEN_01",
                "name": "Abandoned Kitchen",
                "description": "There is a golden_key here. Do not double prefix ##golden_key."
            }
        ],
        "exits": [
            {
                "from_scene_id": "KITCHEN_01",
                "to_scene_id": "CELLAR",
                "label": "door locked with golden_key",
                "lock_description": "Requires golden_key.",
                "rule_to_unlock": "Insert golden_key."
            }
        ],
        "npcs": [
            {
                "id": "GOBLIN",
                "name": "Goblin",
                "description": "A goblin guarding the golden_key.",
                "goal": "Steal the golden_key.",
                "character": "Obsessed with golden_key.",
                "spatial_position": "Holding the golden_key.",
                "reveal_rule": "Goblin shows up when you take the golden_key."
            }
        ],
        "objects": [
            {
                "id": "GOLDEN_KEY",
                "name": "Golden Key",
                "description": "A golden_key that is shiny.",
                "spatial_position": "Under the golden_key.",
                "reveal_rule": "Search pots.",
                "text_log_content": "This note mentions the golden_key.",
                "rule_to_unlock": "Unlock with golden_key."
            }
        ],
        "quests": [
            {
                "id": "GET_KEY",
                "title": "Get the golden_key",
                "description": "Find the golden_key.",
                "goal": "Acquire the golden_key.",
                "impact": "Now you have the golden_key."
            }
        ],
        "awards": [
            {
                "key": "KEY_FINDER",
                "title": "Golden Key Finder",
                "description": "Found the golden_key.",
                "requirement": "Acquire the golden_key."
            }
        ]
    }

    world_generator.WorldGenerator.preprocess_manifest_object_ids(manifest)

    # Assertions for replacements
    assert manifest["teaser"] == "Get the ##GOLDEN_KEY."
    assert manifest["plot"] == "The plot centers on the ##GOLDEN_KEY."
    assert manifest["intro_text"] == "You start with a ##GOLDEN_KEY."
    assert manifest["walkthrough"] == "Use the ##GOLDEN_KEY to unlock the exit."
    assert manifest["completed_condition"] == "Have ##GOLDEN_KEY."
    assert manifest["gameover_condition"] == "Lose the ##GOLDEN_KEY."
    assert manifest["tts_director_notes"] == "Emphasize the ##GOLDEN_KEY."

    assert manifest["protagonist"]["description"] == "A chef carrying a ##GOLDEN_KEY in his pocket."
    assert manifest["protagonist"]["goal"] == "Find the ##GOLDEN_KEY."
    assert manifest["protagonist"]["character"] == "Searches for ##GOLDEN_KEY."

    assert manifest["scenes"][0]["description"] == "There is a ##GOLDEN_KEY here. Do not double prefix ##golden_key."

    assert manifest["exits"][0]["label"] == "door locked with ##GOLDEN_KEY"
    assert manifest["exits"][0]["lock_description"] == "Requires ##GOLDEN_KEY."
    assert manifest["exits"][0]["rule_to_unlock"] == "Insert ##GOLDEN_KEY."

    assert manifest["npcs"][0]["description"] == "A goblin guarding the ##GOLDEN_KEY."
    assert manifest["npcs"][0]["goal"] == "Steal the ##GOLDEN_KEY."
    assert manifest["npcs"][0]["character"] == "Obsessed with ##GOLDEN_KEY."
    assert manifest["npcs"][0]["spatial_position"] == "Holding the ##GOLDEN_KEY."
    assert manifest["npcs"][0]["reveal_rule"] == "Goblin shows up when you take the ##GOLDEN_KEY."

    assert manifest["objects"][0]["description"] == "A ##GOLDEN_KEY that is shiny."
    assert manifest["objects"][0]["spatial_position"] == "Under the ##GOLDEN_KEY."
    assert manifest["objects"][0]["reveal_rule"] == "Search pots."  # Does not contain GOLDEN_KEY
    assert manifest["objects"][0]["text_log_content"] == "This note mentions the ##GOLDEN_KEY."
    assert manifest["objects"][0]["rule_to_unlock"] == "Unlock with ##GOLDEN_KEY."

    assert manifest["quests"][0]["title"] == "Get the ##GOLDEN_KEY"
    assert manifest["quests"][0]["description"] == "Find the ##GOLDEN_KEY."
    assert manifest["quests"][0]["goal"] == "Acquire the ##GOLDEN_KEY."
    assert manifest["quests"][0]["impact"] == "Now you have the ##GOLDEN_KEY."

    assert manifest["awards"][0]["title"] == "Golden Key Finder"  # Does not contain golden_key
    assert manifest["awards"][0]["description"] == "Found the ##GOLDEN_KEY."
    assert manifest["awards"][0]["requirement"] == "Acquire the ##GOLDEN_KEY."

