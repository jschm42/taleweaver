"""Unit tests for script and guard syntax validation in structural validation."""

from backend.core.script_validator import check_scripts_and_guards
from backend.core.world_validator import validate_adventure


def _valid_base_payload(**overrides):
    base = {
        "adventure": {
            "title": "Script Test Adventure",
            "start_scene_id": "START",
            "rule_enforcement_mode": "rpg",
            "generate_scene_images": False,
            "generate_npc_images": False,
            "generate_item_images": False,
            "teaser": "A teaser",
            "rules": "x" * 200,
            "plot": "Plot",
            "intro_text": "Intro",
            "walkthrough": "x" * 100,
            "completed_condition": "Done",
            "gameover_condition": "Lost",
            "tts_director_notes": "Notes",
            "quests": [],
            "sequences": [],
            "awards": [],
        },
        "scenes": [{"id": "START", "label": "Start", "decorative_objects": []}],
        "npcs": [],
        "objects": [],
        "exits": [],
        "entities_all": [],
    }
    for k, v in overrides.items():
        base[k] = v
    return base


def test_valid_scripts_and_guards_emit_no_syntax_findings():
    payload = _valid_base_payload()
    payload["adventure"]["init_script"] = (
        "tw.vars.set('score', 0)\ndef helper(x):\n    return x * 2"
    )
    payload["adventure"]["completed_guard_expression"] = "tw.vars.get('score') > 10"
    payload["adventure"]["gameover_guard_expression"] = "tw.player.hp <= 0"
    payload["adventure"]["scripts"] = [
        {"id": "on_turn_tick", "trigger": "on_turn_start", "code": "tw.vars.set('score', 1)"}
    ]
    payload["scenes"][0]["on_enter_scene_script"] = "tw.player.send_message('Welcome!')"
    payload["scenes"][0]["on_leave_scene_script"] = "tw.vars.set('left_start', True)"

    findings = check_scripts_and_guards(payload)
    assert findings == []


def test_invalid_init_script_syntax():
    payload = _valid_base_payload()
    payload["adventure"]["init_script"] = "def bad_func(\n    return 42"
    findings = check_scripts_and_guards(payload)
    errs = [f for f in findings if f.code == "script_syntax_error"]
    assert len(errs) == 1
    assert errs[0].severity == "error"
    assert errs[0].location == "adventure"
    assert errs[0].context.get("field") == "init_script"


def test_sandbox_security_violation_in_script():
    payload = _valid_base_payload()
    payload["adventure"]["init_script"] = "import os\nos.system('calc')"
    findings = check_scripts_and_guards(payload)
    errs = [f for f in findings if f.code == "script_syntax_error"]
    assert len(errs) == 1
    assert "Forbidden syntax 'Import'" in errs[0].message


def test_invalid_modular_script():
    payload = _valid_base_payload()
    payload["adventure"]["scripts"] = [
        {"id": "test_script", "trigger": "on_enter", "code": "if True\n    pass"}
    ]
    findings = check_scripts_and_guards(payload)
    errs = [f for f in findings if f.code == "script_syntax_error"]
    assert len(errs) == 1
    assert errs[0].location == "script:test_script"
    assert errs[0].context.get("script_id") == "test_script"


def test_invalid_top_level_guard_expressions():
    payload = _valid_base_payload()
    # Statements / syntax errors are not valid in mode='eval'
    payload["adventure"]["completed_guard_expression"] = "score = 10"
    payload["adventure"]["gameover_guard_expression"] = "for x in items: pass"
    findings = check_scripts_and_guards(payload)
    guard_errs = [f for f in findings if f.code == "guard_syntax_error"]
    assert len(guard_errs) == 2
    assert all(f.severity == "error" for f in guard_errs)
    fields = {f.context.get("field") for f in guard_errs}
    assert fields == {"completed_guard_expression", "gameover_guard_expression"}


def test_scene_scripts_syntax():
    payload = _valid_base_payload()
    payload["scenes"].append(
        {
            "id": "CAVE",
            "label": "Cave",
            "on_enter_scene_script": "tw.vars.set('entered_cave', True",  # missing paren
            "on_leave_scene_script": "tw.vars.get(__private_val)",  # dunder variable forbidden
        }
    )
    findings = check_scripts_and_guards(payload)
    scene_errs = [f for f in findings if f.location == "scene:CAVE"]
    assert len(scene_errs) == 2
    fields = {f.context.get("field") for f in scene_errs}
    assert fields == {"on_enter_scene_script", "on_leave_scene_script"}


def test_exit_scripts_and_guards():
    payload = _valid_base_payload()
    payload["exits"].append(
        {
            "id": "DOOR_1",
            "from_scene_id": "START",
            "to_scene_id": "START",
            "unlock_expression": "tw.switches.get('GATE' == 'OPEN'",  # missing paren
            "on_open_exit_script": "if x: return\nelse",  # invalid syntax
        }
    )
    findings = check_scripts_and_guards(payload)
    exit_guard_errs = [
        f for f in findings if f.code == "guard_syntax_error" and f.location == "exit:DOOR_1"
    ]
    exit_script_errs = [
        f for f in findings if f.code == "script_syntax_error" and f.location == "exit:DOOR_1"
    ]
    assert len(exit_guard_errs) == 1
    assert exit_guard_errs[0].context.get("field") == "unlock_expression"
    assert len(exit_script_errs) == 1
    assert exit_script_errs[0].context.get("field") == "on_open_exit_script"


def test_npc_scripts_syntax():
    payload = _valid_base_payload()
    payload["npcs"].append(
        {
            "id": "DRAGON",
            "entity_type": "NPC",
            "name": "Dragon",
            "description": "Fierce dragon",
            "on_defeat_script": "def defeat(\n    pass",
        }
    )
    findings = check_scripts_and_guards(payload)
    npc_errs = [f for f in findings if f.location == "entity:DRAGON"]
    assert len(npc_errs) == 1
    assert npc_errs[0].code == "script_syntax_error"
    assert npc_errs[0].context.get("field") == "on_defeat_script"


def test_object_constructable_and_switch_syntax():
    payload = _valid_base_payload()
    payload["objects"].append(
        {
            "id": "MAGIC_SWORD",
            "entity_type": "OBJECT",
            "name": "Magic Sword",
            "description": "Constructable sword",
            "item_type": "CONSTRUCTABLE",
            "craft_guard_expression": "tw.player.level >= 5 and",  # trailing and
            "on_craft_success_script": "tw.player.give_item('MAGIC_SWORD'",  # missing paren
        }
    )
    payload["objects"].append(
        {
            "id": "LEVER",
            "entity_type": "OBJECT",
            "name": "Lever",
            "description": "Switch lever",
            "item_type": "SWITCH",
            "switch_transitions": [
                {
                    "from_state": "OFF",
                    "to_state": "ON",
                    "expression": "tw.vars.get('lever_unlocked' == True",  # syntax error in guard
                    "on_success_script": "tw.vars.set('gate_opened', True)",  # valid
                    "on_failure_script": "raise RuntimeError('Boom')",  # raise is forbidden in sandbox
                }
            ],
        }
    )
    findings = check_scripts_and_guards(payload)
    sword_errs = [f for f in findings if f.location == "entity:MAGIC_SWORD"]
    assert len(sword_errs) == 2

    lever_errs = [f for f in findings if f.location == "entity:LEVER"]
    assert len(lever_errs) == 2  # 1 guard error, 1 script error (raise is forbidden)


def test_sequence_quest_and_award_guards():
    payload = _valid_base_payload()
    payload["adventure"]["sequences"] = [
        {
            "id": "SEQ_1",
            "guard_expression": "tw.vars.get('step_1') = True",  # single = assignment in eval
            "on_start_sequence_script": "tw.send('Start')",  # valid
        }
    ]
    payload["adventure"]["quests"] = [
        {
            "id": "QUEST_1",
            "guard_expression": "tw.player.has_item('KEY' == True",  # missing paren
        }
    ]
    payload["adventure"]["awards"] = [
        {
            "key": "AWARD_HERO",
            "guard_expression": "import sys",  # forbidden import in guard
        }
    ]
    findings = check_scripts_and_guards(payload)
    seq_errs = [f for f in findings if f.location == "sequence:SEQ_1"]
    quest_errs = [f for f in findings if f.location == "quest:QUEST_1"]
    award_errs = [f for f in findings if f.location == "award:AWARD_HERO"]

    assert len(seq_errs) == 1
    assert seq_errs[0].code == "guard_syntax_error"
    assert len(quest_errs) == 1
    assert quest_errs[0].code == "guard_syntax_error"
    assert len(award_errs) == 1
    assert award_errs[0].code == "guard_syntax_error"


def test_protagonist_scripts():
    payload = _valid_base_payload()
    payload["protagonist"] = {
        "stats": {
            "on_hp_change_script": "if tw.player.hp < 10\n    tw.send('Low HP!')",  # missing colon
        }
    }
    findings = check_scripts_and_guards(payload)
    prot_errs = [f for f in findings if f.location == "protagonist"]
    assert len(prot_errs) == 1
    assert prot_errs[0].code == "script_syntax_error"


def test_validate_adventure_integrates_script_checks():
    payload = _valid_base_payload()
    payload["adventure"]["init_script"] = "invalid python code :("
    payload["adventure"]["completed_guard_expression"] = "tw.vars.get('win' == 1"

    findings = validate_adventure(payload)
    script_findings = [
        f for f in findings if f.code in {"script_syntax_error", "guard_syntax_error"}
    ]
    assert len(script_findings) == 2
    # Errors should be sorted first
    assert all(f.severity == "error" for f in script_findings)
