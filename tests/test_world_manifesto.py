from backend.engine.world import world_generator


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
                "Head": "",
                "Chest": "",
                "Hands": "",
                "Legs": "",
                "Feet": "",
                "Neck": "",
                "Ring_1": "",
                "Ring_2": "",
                "MainHand": "",
                "OffHand": "",
            },
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
            {
                "id": "KITCHEN_01",
                "name": "Abandoned Kitchen",
                "description": "Dusty pots and a cold hearth.",
            }
        ],
        "exits": [],
        "npcs": [],
        "objects": [],
        "quests": [],
        "awards": [],
        "sequences": [],
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
            "strength": 10,
            "dexterity": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10,
            "armor_class": 10,
            "hp": 100,
            "mana": 100,
            "stamina": 100,
            "starting_inventory": [],
            "starting_equipment": {
                "Head": "",
                "Chest": "",
                "Hands": "",
                "Legs": "",
                "Feet": "",
                "Neck": "",
                "Ring_1": "",
                "Ring_2": "",
                "MainHand": "",
                "OffHand": "",
            },
        },
        "teaser": "Get the golden_key.",
        "language": "English",
        "origin_id": "",
        "plot": "The plot centers on the golden_key.",
        "rules": "",
        "intro_text": "You start with a golden_key.",
        "completed_condition": "Have golden_key.",
        "gameover_condition": "Lose the golden_key.",
        "sequences": [
            {
                "title": "Escape",
                "description": "Find the golden_key.",
                "walkthrough": "Use the GOLDEN_KEY to unlock the exit.",
                "end_condition": "Have golden_key.",
            }
        ],
        "scenes": [
            {
                "id": "KITCHEN_01",
                "name": "Abandoned Kitchen",
                "description": "There is a golden_key here. Do not double prefix ##golden_key.",
            }
        ],
        "exits": [
            {
                "from_scene_id": "KITCHEN_01",
                "to_scene_id": "CELLAR",
                "label": "door locked with golden_key",
                "lock_description": "Requires golden_key.",
                "rule_to_unlock": "Insert golden_key.",
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
                "reveal_rule": "Goblin shows up when you take the golden_key.",
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
                "rule_to_unlock": "Unlock with golden_key.",
            }
        ],
        "quests": [
            {
                "id": "GET_KEY",
                "title": "Get the golden_key",
                "description": "Find the golden_key.",
                "goal": "Acquire the golden_key.",
                "impact": "Now you have the golden_key.",
            }
        ],
        "awards": [
            {
                "key": "KEY_FINDER",
                "title": "Golden Key Finder",
                "description": "Found the golden_key.",
                "requirement": "Acquire the golden_key.",
            }
        ],
    }

    world_generator.WorldGenerator.preprocess_manifest_object_ids(manifest)

    # Assertions for replacements
    assert manifest["teaser"] == "Get the ##GOLDEN_KEY."
    assert manifest["plot"] == "The plot centers on the ##GOLDEN_KEY."
    assert manifest["intro_text"] == "You start with a ##GOLDEN_KEY."
    assert manifest["completed_condition"] == "Have ##GOLDEN_KEY."
    assert manifest["gameover_condition"] == "Lose the ##GOLDEN_KEY."
    assert manifest["sequences"][0]["walkthrough"] == "Use the ##GOLDEN_KEY to unlock the exit."
    assert manifest["sequences"][0]["description"] == "Find the ##GOLDEN_KEY."

    assert manifest["protagonist"]["description"] == "A chef carrying a ##GOLDEN_KEY in his pocket."
    assert manifest["protagonist"]["goal"] == "Find the ##GOLDEN_KEY."
    assert manifest["protagonist"]["character"] == "Searches for ##GOLDEN_KEY."

    assert (
        manifest["scenes"][0]["description"]
        == "There is a ##GOLDEN_KEY here. Do not double prefix ##golden_key."
    )

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


def test_world_manifesto_tolerates_null_optional_fields():
    """Verify that WorldManifesto and entities gracefully handle null (None) values from LLM responses."""
    manifest = {
        "protagonist": {
            "name": "Detective Jack Steele",
            "role": "Undercover Detective",
            "description": "A hard-boiled detective in a rumpled trench coat.",
            "goal": "Solve the mystery.",
            "character": "Cynical but thorough.",
            "strength": 12,
            "dexterity": 14,
            "intelligence": 15,
            "wisdom": 13,
            "charisma": 11,
            "armor_class": 12,
            "hp": 90,
            "mana": 50,
            "stamina": 80,
            "starting_inventory": None,
            "starting_equipment": {
                "Head": None,
                "Chest": None,
                "Hands": None,
                "Legs": None,
                "Feet": None,
                "Neck": None,
                "Ring_1": None,
                "Ring_2": None,
                "MainHand": None,
                "OffHand": None,
            },
            "on_hp_change_script": None,
            "on_hp_change_text": None,
            "on_status_change_script": None,
            "on_status_change_text": None,
        },
        "teaser": "Solve the murder at midnight.",
        "language": "English",
        "origin_id": "",
        "plot": "Track down the syndicate boss.",
        "rules": "",
        "intro_text": None,
        "completed_condition": None,
        "gameover_condition": None,
        "completed_guard_expression": None,
        "gameover_guard_expression": None,
        "scenes": [
            {
                "id": "ALLEY_01",
                "name": "Dark Alley",
                "description": "Rain trickles down the fire escapes.",
                "on_enter_scene_script": None,
                "on_enter_scene_text": None,
                "on_leave_scene_script": None,
                "on_leave_scene_text": None,
            }
        ],
        "exits": [
            {
                "from_scene_id": "ALLEY_01",
                "to_scene_id": "STREET_01",
                "label": "iron gate",
                "is_locked": False,
                "lock_description": None,
                "code_to_unlock": None,
                "item_to_unlock": None,
                "rule_to_unlock": None,
                "on_open_exit_script": None,
                "on_open_exit_text": None,
                "on_exit_used_script": None,
                "on_exit_used_text": None,
                "unlock_expression": None,
                "on_unlock_success_script": None,
                "on_unlock_success_text": None,
                "on_unlock_failure_script": None,
                "on_unlock_failure_text": None,
            }
        ],
        "npcs": [
            {
                "id": "INFORMANT",
                "name": "Slick Larry",
                "description": "Leaning against the damp brick wall.",
                "goal": "Stay alive.",
                "character": "Shifty.",
                "start_scene_id": "ALLEY_01",
                "spatial_position": "shadows",
                "npc_type": "HUMANOID",
                "hp": 40,
                "mana": 0,
                "stamina": 50,
                "is_attackable": True,
                "is_killable": True,
                "is_hidden": False,
                "reveal_rule": None,
                "inventory": None,
                "on_defeat_script": None,
                "on_defeat_text": None,
                "on_protagonist_enters_scene_script": None,
                "on_protagonist_enters_scene_text": None,
            }
        ],
        "objects": [
            {
                "id": f"OBJ_{i}",
                "name": f"Object {i}",
                "description": f"Description {i}",
                "start_scene_id": "ALLEY_01",
                "spatial_position": "on the pavement",
                "item_type": "SWITCH" if i == 24 else "PICKABLE",
                "wearable_slots": None,
                "is_hidden": False,
                "reveal_rule": None,
                "is_portable": True,
                "code_to_unlock": None,
                "item_to_unlock": None,
                "rule_to_unlock": None,
                "reveals_item_id": None,
                "text_log_content": None,
                "text_log_format": None,
                "switch_initial_state": None,
                "on_success_script": None,
                "on_failure_script": None,
                "on_pickup_script": None,
                "on_pickup_text": None,
                "on_drop_script": None,
                "on_drop_text": None,
                "on_equip_script": None,
                "on_equip_text": None,
                "on_unequip_script": None,
                "on_unequip_text": None,
                "unlock_expression": None,
                "on_unlock_success_script": None,
                "on_unlock_success_text": None,
                "on_unlock_failure_script": None,
                "on_unlock_failure_text": None,
                "on_read_script": None,
                "on_read_text": None,
                "craft_guard_expression": None,
                "on_craft_success_script": None,
                "on_craft_success_text": None,
                "on_craft_failure_script": None,
                "on_craft_failure_text": None,
            }
            for i in range(26)
        ],
        "sequences": [
            {
                "id": "SEQ_1",
                "order": 1,
                "title": "Start",
                "description": None,
                "walkthrough": None,
                "end_condition": None,
                "required_item_id": None,
                "required_scene_id": None,
                "required_defeated_npc_id": None,
                "guard_expression": None,
                "on_start_sequence_script": None,
                "on_start_sequence_text": None,
                "on_end_sequence_script": None,
                "on_end_sequence_text": None,
            }
        ],
        "quests": [],
        "awards": [],
    }

    manifesto = world_generator.WorldManifesto.model_validate(manifest)
    assert manifesto.protagonist.name == "Detective Jack Steele"
    assert manifesto.protagonist.starting_inventory == []
    assert manifesto.protagonist.starting_equipment.Head == ""
    assert len(manifesto.objects) == 26
    obj_24 = manifesto.objects[24]
    assert obj_24.on_failure_script == ""
    assert obj_24.on_success_script == ""
    assert obj_24.wearable_slots == []
    assert manifesto.intro_text == ""
