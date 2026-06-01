from backend.core import prompts
from backend.engine.world_generator import WorldObjectSchema


def test_world_generation_prompt_mentions_switch_item_type() -> None:
    system_prompt = prompts.WORLD_GENERATION_SYSTEM_PROMPT
    assert "item_type" in system_prompt
    assert "SWITCH" in system_prompt
    assert "switch_transitions" in system_prompt


def test_world_object_schema_accepts_switch_fields() -> None:
    payload = {
        "id": "SW_POWER_CORE",
        "name": "Power Regulator",
        "description": "A hardened switch console with two stable states.",
        "start_scene_id": "ENGINE_ROOM",
        "spatial_position": "mounted on the north wall",
        "item_type": "SWITCH",
        "wearable_slots": [],
        "is_hidden": False,
        "reveal_rule": "",
        "is_portable": False,
        "code_to_unlock": "",
        "item_to_unlock": "",
        "rule_to_unlock": "",
        "combination_ingredients": [],
        "reveals_item_id": "",
        "stat_modifier_strength": 0,
        "stat_modifier_dexterity": 0,
        "stat_modifier_intelligence": 0,
        "stat_modifier_wisdom": 0,
        "stat_modifier_charisma": 0,
        "stat_modifier_armor_class": 0,
        "hp_change": 0,
        "stamina_change": 0,
        "mana_change": 0,
        "inventory": [],
        "text_log_content": "",
        "text_log_format": "",
        "switch_states": ["LOW", "HIGH"],
        "switch_initial_state": "LOW",
        "switch_transitions": [
            {
                "from": "LOW",
                "to": "HIGH",
                "gates": {"item": None, "code": "7391", "rule": None},
                "fail_message": "Wrong access code.",
            }
        ],
        "switch_outcomes": [
            {
                "on_state": "HIGH",
                "effects": [{"type": "unlock_exit", "target_id": "EXIT_ENGINE_HALL"}],
            }
        ],
    }

    obj = WorldObjectSchema(**payload)
    assert obj.item_type == "SWITCH"
    assert obj.switch_states == ["LOW", "HIGH"]
    assert len(obj.switch_transitions) == 1
