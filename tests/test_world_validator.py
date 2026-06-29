"""Unit tests for the structural world validator."""

from backend.core.world_validator import validate_adventure


def _empty_adventure(**overrides):
    """Build a minimal-but-valid editor payload."""
    base = {
        "adventure": {
            "title": "Test",
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
        },
        "scenes": [{"id": "START", "label": "Start", "decorative_objects": []}],
        "npcs": [],
        "objects": [],
        "exits": [],
        "entities_all": [],
    }
    for k, v in overrides.items():
        base[k] = v
    base["adventure"].update(overrides.get("adventure_overrides", {}))
    return base


def _codes(findings, code):
    return [f for f in findings if f.code == code]


def test_empty_adventure_emits_no_findings():
    findings = validate_adventure(_empty_adventure())
    assert findings == [], f"unexpected findings: {[f.code for f in findings]}"


def test_missing_start_scene_emits_error():
    payload = _empty_adventure()
    payload["adventure"]["start_scene_id"] = "GONE"
    findings = validate_adventure(payload)
    assert any(f.code == "missing_start_scene" and f.severity == "error" for f in findings)


def test_unreachable_scene_emits_error():
    payload = _empty_adventure()
    payload["scenes"].append({"id": "DEAD", "label": "Dead end"})
    findings = validate_adventure(payload)
    dead = _codes(findings, "unreachable_scene")
    assert len(dead) == 1
    assert dead[0].severity == "error"
    assert dead[0].location == "scene:DEAD"


def test_unreachable_scene_ignores_one_way_exits():
    payload = _empty_adventure()
    payload["scenes"].append({"id": "FAR", "label": "Far away"})
    payload["exits"].append({
        "id": "ex1",
        "from_scene_id": "FAR",
        "to_scene_id": "START",
        "exit_type": "one_way",
    })
    findings = validate_adventure(payload)
    unreachable = _codes(findings, "unreachable_scene")
    assert any(f.location == "scene:FAR" for f in unreachable) is True


def test_exit_to_missing_scene_emits_error():
    payload = _empty_adventure()
    payload["exits"].append({
        "id": "ex1",
        "from_scene_id": "START",
        "to_scene_id": "NOWHERE",
        "exit_type": "bidirectional",
    })
    findings = validate_adventure(payload)
    miss = _codes(findings, "exit_to_missing_scene")
    assert len(miss) == 1
    assert miss[0].severity == "error"


def test_duplicate_scene_id_emits_error():
    payload = _empty_adventure()
    payload["scenes"].append({"id": "START", "label": "Dupe"})
    findings = validate_adventure(payload)
    dup = _codes(findings, "duplicate_scene_id")
    assert len(dup) == 1


def test_missing_item_ref_emits_error():
    payload = _empty_adventure()
    payload["objects"].append({
        "id": "chest_01",
        "entity_type": "OBJECT",
        "item_type": "CONTAINER",
        "item_to_unlock": "GOLDEN_KEY",
    })
    payload["entities_all"] = payload["objects"]
    findings = validate_adventure(payload)
    miss = _codes(findings, "missing_item_ref")
    assert len(miss) == 1
    assert miss[0].severity == "error"
    assert miss[0].location == "entity:chest_01"


def test_container_inventory_orphan_emits_error():
    payload = _empty_adventure()
    payload["objects"].append({
        "id": "chest_01",
        "entity_type": "OBJECT",
        "item_type": "CONTAINER",
        "inventory": [{"item_id": "PHANTOM_GOLD"}],
    })
    payload["entities_all"] = payload["objects"]
    findings = validate_adventure(payload)
    miss = _codes(findings, "container_inventory_orphan")
    assert len(miss) == 1


def test_locked_but_no_unlock_key_emits_warn():
    payload = _empty_adventure()
    payload["objects"].append({
        "id": "chest_01",
        "entity_type": "OBJECT",
        "item_type": "CONTAINER",
        "metadata_json": {"locked": True},
    })
    payload["entities_all"] = payload["objects"]
    findings = validate_adventure(payload)
    miss = _codes(findings, "locked_but_no_unlock_key")
    assert len(miss) == 1
    assert miss[0].severity == "warn"


def test_npc_zero_stats_emits_warn():
    payload = _empty_adventure()
    payload["npcs"].append({
        "id": "rat_1",
        "entity_type": "NPC",
        "npc_type": "ANIMAL",
        "hp": 0,
        "stamina": 0,
        "mana": 0,
    })
    payload["entities_all"] = payload["npcs"]
    findings = validate_adventure(payload)
    miss = _codes(findings, "npc_zero_stats")
    assert len(miss) == 1


def test_npc_overpowered_emits_warn():
    payload = _empty_adventure()
    payload["npcs"].append({
        "id": "dragon",
        "entity_type": "NPC",
        "npc_type": "MONSTER",
        "hp": 999,
        "stamina": 200,
        "mana": 200,
        "strength": 50,
        "armor_class": 30,
    })
    payload["entities_all"] = payload["npcs"]
    findings = validate_adventure(payload)
    miss = _codes(findings, "npc_overpowered")
    assert len(miss) == 1


def test_image_coverage_emits_warn_when_enabled_and_missing():
    payload = _empty_adventure(
        adventure_overrides={"generate_scene_images": True},
    )
    # First scene has no image_url
    findings = validate_adventure(payload)
    miss = _codes(findings, "scene_image_coverage")
    assert len(miss) == 1
    assert miss[0].context["missing_count"] == 1
    assert miss[0].context["total_count"] == 1


def test_rpg_mode_with_combatants_emits_warn_in_chat_mode():
    payload = _empty_adventure(
        adventure_overrides={"rule_enforcement_mode": "chat"},
    )
    payload["npcs"].append({
        "id": "guard_1",
        "entity_type": "NPC",
        "npc_type": "HUMANOID",
        "hp": 50,
        "stamina": 50,
        "mana": 0,
        "is_attackable": True,
    })
    payload["entities_all"] = payload["npcs"]
    findings = validate_adventure(payload)
    miss = _codes(findings, "rpg_mode_required_for_combat")
    assert len(miss) == 1


def test_decorative_objects_overflow_emits_warn():
    payload = _empty_adventure()
    payload["scenes"][0]["decorative_objects"] = [f"item_{i}" for i in range(8)]
    findings = validate_adventure(payload)
    miss = _codes(findings, "decorative_objects_overflow")
    assert len(miss) == 1


def test_switch_missing_states_emits_warn():
    payload = _empty_adventure()
    payload["objects"].append({
        "id": "switch_01",
        "entity_type": "OBJECT",
        "item_type": "SWITCH",
        "switch_states": ["on"],
        "switch_initial_state": "on",
    })
    payload["entities_all"] = payload["objects"]
    findings = validate_adventure(payload)
    miss = _codes(findings, "switch_missing_states")
    assert len(miss) == 1


def test_switch_unreachable_state_emits_warn():
    payload = _empty_adventure()
    payload["objects"].append({
        "id": "switch_01",
        "entity_type": "OBJECT",
        "item_type": "SWITCH",
        "switch_states": ["on", "off"],
        "switch_initial_state": "BROKEN",
    })
    payload["entities_all"] = payload["objects"]
    findings = validate_adventure(payload)
    miss = _codes(findings, "switch_unreachable_state")
    assert len(miss) == 1


def test_exit_without_label_emits_warn():
    payload = _empty_adventure()
    payload["exits"].append({
        "id": "ex1",
        "from_scene_id": "START",
        "to_scene_id": "START",
        "label": "",
    })
    findings = validate_adventure(payload)
    miss = _codes(findings, "exit_without_label")
    assert len(miss) == 1


def test_empty_story_fields_emit_warnings():
    payload = _empty_adventure(
        adventure_overrides={
            "teaser": "",
            "plot": "",
            "intro_text": "",
            "walkthrough": "",
            "completed_condition": "",
            "gameover_condition": "",
            "tts_director_notes": "",
            "rules": "x" * 200,  # long enough to not trigger rules_too_short
        },
    )
    findings = validate_adventure(payload)
    fields = {f.context.get("field") for f in _codes(findings, "empty_story_field")}
    expected = {"teaser", "plot", "intro_text", "walkthrough",
                "completed_condition", "gameover_condition", "tts_director_notes"}
    assert expected.issubset(fields)


def test_rules_too_short_emits_warn():
    payload = _empty_adventure(
        adventure_overrides={"rules": "short"},
    )
    findings = validate_adventure(payload)
    miss = _codes(findings, "rules_too_short")
    assert len(miss) == 1


def test_findings_sorted_errors_first_then_by_code():
    payload = _empty_adventure()
    payload["exits"].append({
        "id": "ex1",
        "from_scene_id": "START",
        "to_scene_id": "NOWHERE",
        "label": "",
    })
    findings = validate_adventure(payload)
    severities = [f.severity for f in findings]
    # All errors must precede all warns.
    last_error_index = max((i for i, s in enumerate(severities) if s == "error"), default=-1)
    first_warn_index = next((i for i, s in enumerate(severities) if s == "warn"), len(severities))
    assert last_error_index < first_warn_index


def test_quest_references_missing_entity_emits_error():
    payload = _empty_adventure(
        adventure_overrides={
            "quests": [{"id": "q1", "target_object_id": "PHANTOM_KEY"}],
        },
    )
    findings = validate_adventure(payload)
    miss = _codes(findings, "quest_references_missing_entity")
    assert len(miss) == 1


def test_container_inventory_too_large_emits_warn():
    payload = _empty_adventure()
    payload["objects"].append({
        "id": "chest_01",
        "entity_type": "OBJECT",
        "item_type": "CONTAINER",
        "inventory": [{"item_id": f"x_{i}"} for i in range(15)],
    })
    payload["entities_all"] = payload["objects"]
    findings = validate_adventure(payload)
    miss = _codes(findings, "container_inventory_too_large")
    assert len(miss) == 1
    assert miss[0].context["count"] == 15