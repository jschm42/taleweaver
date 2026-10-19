"""Unit tests for reference, placement, and progression checks of the world validator."""

from backend.core.world_validator import validate_adventure
from tests.test_world_validator import _codes, _empty_adventure


def _with_entities(*entities, **overrides):
    payload = _empty_adventure(**overrides)
    payload["entities_all"] = list(entities)
    return payload


def _item(eid, scene="START", **fields):
    return {"id": eid, "entity_type": "OBJECT", "current_scene_id": scene, **fields}


def _npc(eid, scene="START", **fields):
    return {"id": eid, "entity_type": "NPC", "current_scene_id": scene, **fields}


def _exit(from_id, to_id, **fields):
    return {
        "id": f"{from_id}_{to_id}",
        "from_scene_id": from_id,
        "to_scene_id": to_id,
        "label": "door",
        "exit_type": "bidirectional",
        **fields,
    }


# ---------------------------------------------------------------------------
# Scene graph and exits
# ---------------------------------------------------------------------------


def test_exit_without_exit_type_is_one_way_like_the_engine():
    # Arrange: the engine only walks exits backwards when exit_type == 'bidirectional'.
    payload = _empty_adventure()
    payload["scenes"].append({"id": "BACK", "label": "Back"})
    payload["exits"].append(_exit("BACK", "START", exit_type=None))

    # Act
    findings = validate_adventure(payload)

    # Assert
    assert [f.location for f in _codes(findings, "unreachable_scene")] == ["scene:BACK"]


def test_exit_key_item_missing_and_locked_without_key():
    # Arrange
    payload = _empty_adventure()
    payload["scenes"] += [{"id": "A"}, {"id": "B"}]
    payload["exits"] += [
        _exit("START", "A", is_locked=True, item_to_unlock="GHOST_KEY"),
        _exit("START", "B", is_locked=True),
    ]

    # Act
    findings = validate_adventure(payload)

    # Assert
    assert _codes(findings, "exit_key_item_missing")[0].context["missing_ref"] == "GHOST_KEY"
    assert _codes(findings, "exit_locked_without_key")[0].location == "exit:START_B"


def test_scene_and_entity_sharing_an_id_is_an_error():
    findings = validate_adventure(_with_entities(_item("START")))
    assert len(_codes(findings, "scene_entity_id_clash")) == 1


# ---------------------------------------------------------------------------
# Placement
# ---------------------------------------------------------------------------


def test_entity_in_missing_scene_is_an_error():
    findings = validate_adventure(_with_entities(_npc("GHOST", scene="LIMBO")))
    miss = _codes(findings, "entity_in_missing_scene")
    assert len(miss) == 1
    assert miss[0].severity == "error"


def test_items_in_containers_and_inventories_are_placed_correctly():
    # Arrange
    payload = _with_entities(
        _item("CHEST", item_type="CONTAINER", inventory=["COIN"]),
        _item("COIN", scene="CHEST"),
        _item("SWORD", scene="INVENTORY"),
        _item("LOST", scene="INVENTORY"),
    )
    payload["protagonist"] = {"inventory": ["SWORD"], "equipment": {"Head": None}}

    # Act
    findings = validate_adventure(payload)

    # Assert
    assert _codes(findings, "entity_in_missing_scene") == []
    orphans = _codes(findings, "inventory_item_without_owner")
    assert [f.context["entity_id"] for f in orphans] == ["LOST"]


def test_npc_allowed_scene_missing_emits_warn():
    findings = validate_adventure(
        _with_entities(_npc("WANDERER", allowed_scenes=["START", "NOPE"]))
    )
    miss = _codes(findings, "npc_allowed_scene_missing")
    assert [f.context["missing_scene"] for f in miss] == ["NOPE"]


# ---------------------------------------------------------------------------
# Item references
# ---------------------------------------------------------------------------


def test_npc_inventory_and_equipment_must_exist():
    # Arrange
    npc = _npc(
        "KNIGHT",
        inventory=[{"id": "SHIELD"}, {"id": "GONE"}],
        metadata_json={"equipped_weapon_id": "LOST_BLADE"},
    )
    payload = _with_entities(npc, _item("SHIELD"))

    # Act
    findings = validate_adventure(payload)

    # Assert
    missing = {f.context["missing_ref"] for f in _codes(findings, "npc_item_missing")}
    assert missing == {"GONE", "LOST_BLADE"}


def test_reveal_target_missing_emits_error():
    findings = validate_adventure(_with_entities(_item("COUCH", reveals_item_id="BATTERIES")))
    assert len(_codes(findings, "reveal_target_missing")) == 1


def test_protagonist_item_missing_ignores_inline_item_definitions():
    # Arrange
    payload = _with_entities(_item("MAP", scene="INVENTORY"))
    payload["protagonist"] = {
        "inventory": ["MAP", "PHANTOM", {"id": "dyn_1", "name": "Dynamic apple"}],
        "equipment": {"Chest": {"id": "NO_JACKET"}},
    }

    # Act
    findings = validate_adventure(payload)

    # Assert
    missing = {f.context["missing_ref"] for f in _codes(findings, "protagonist_item_missing")}
    assert missing == {"PHANTOM", "NO_JACKET"}


# ---------------------------------------------------------------------------
# Hard rules
# ---------------------------------------------------------------------------


def test_award_special_action_and_attack_trigger_references_are_checked():
    # Arrange
    payload = _with_entities(
        _npc("TROLL", metadata_json={"attack_trigger": {"required_scene_id": "VOID"}}),
        adventure_overrides={
            "awards": [{"key": "brave", "title": "Brave", "required_defeated_npc_id": "DRAGON"}],
        },
    )
    payload["protagonist"] = {
        "stats": {
            "special_actions": [
                {"id": "FIREBALL", "is_locked": True, "unlock_required_item_id": "WAND"},
                {"id": "PUNCH", "is_locked": False, "unlock_required_item_id": "IGNORED"},
            ]
        }
    }

    # Act
    findings = validate_adventure(payload)

    # Assert
    assert _codes(findings, "award_references_missing_npc")[0].location == "award:brave"
    assert len(_codes(findings, "special_action_references_missing_item")) == 1
    assert _codes(findings, "npc_attack_trigger_references_missing_scene")[0].location == (
        "entity:TROLL"
    )


def test_sequence_item_rule_must_reference_an_item_not_an_npc():
    payload = _with_entities(
        _npc("ORACLE"),
        adventure_overrides={
            "sequences": [{"id": "s1", "title": "Ask", "required_item_id": "ORACLE"}]
        },
    )
    findings = validate_adventure(payload)
    assert len(_codes(findings, "sequence_references_missing_item")) == 1


# ---------------------------------------------------------------------------
# Mode-dependent and switch checks
# ---------------------------------------------------------------------------


def test_npc_stats_are_skipped_outside_rpg_mode():
    payload = _with_entities(
        _npc("RAT", hp=0, stamina=0, mana=0),
        adventure_overrides={"rule_enforcement_mode": "story"},
    )
    findings = validate_adventure(payload)
    assert _codes(findings, "npc_zero_stats") == []


def test_npc_without_explicit_hp_is_not_zero():
    findings = validate_adventure(_with_entities(_npc("GUARD", hp=None, stamina=30, mana=0)))
    assert _codes(findings, "npc_zero_stats") == []


def test_switch_without_initial_state_is_not_flagged():
    switch = _item(
        "LEVER", item_type="SWITCH", switch_states=["UP", "DOWN"], switch_initial_state=""
    )
    findings = validate_adventure(_with_entities(switch))
    assert _codes(findings, "switch_unreachable_state") == []


def test_short_walkthrough_emits_warn():
    findings = validate_adventure(_empty_adventure(adventure_overrides={"walkthrough": "Go."}))
    assert len(_codes(findings, "walkthrough_too_short")) == 1


# ---------------------------------------------------------------------------
# Key progression (softlocks)
# ---------------------------------------------------------------------------


def _vault_payload(key_scene, **overrides):
    payload = _with_entities(_item("VAULT_KEY", scene=key_scene), **overrides)
    payload["scenes"].append({"id": "VAULT"})
    payload["exits"].append(_exit("START", "VAULT", is_locked=True, item_to_unlock="VAULT_KEY"))
    return payload


def test_key_locked_behind_its_own_door_is_a_softlock():
    findings = validate_adventure(_vault_payload("VAULT"))
    softlocks = _codes(findings, "exit_key_unobtainable")
    assert [f.context["key_item"] for f in softlocks] == ["VAULT_KEY"]


def test_reachable_key_is_not_a_softlock():
    findings = validate_adventure(_vault_payload("START"))
    assert _codes(findings, "exit_key_unobtainable") == []


def test_key_chain_through_containers_and_npcs_resolves():
    # Arrange: CHEST (opened by RUSTY_KEY, carried by an NPC) holds the vault key.
    payload = _vault_payload("CHEST")
    payload["entities_all"] += [
        _item("CHEST", item_type="CONTAINER", item_to_unlock="RUSTY_KEY", inventory=["VAULT_KEY"]),
        _npc("HERMIT", inventory=["RUSTY_KEY"]),
        _item("RUSTY_KEY", scene="INVENTORY"),
    ]

    # Act
    findings = validate_adventure(payload)

    # Assert
    assert _codes(findings, "exit_key_unobtainable") == []
    assert _codes(findings, "container_key_unobtainable") == []


def test_container_whose_key_is_inside_itself_is_a_softlock():
    payload = _with_entities(
        _item("BOX", item_type="CONTAINER", item_to_unlock="BOX_KEY", inventory=["BOX_KEY"]),
        _item("BOX_KEY", scene="BOX"),
    )
    findings = validate_adventure(payload)
    assert [f.location for f in _codes(findings, "container_key_unobtainable")] == ["entity:BOX"]

