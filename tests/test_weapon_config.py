"""Tests for configurable weapons: attack-roll stat, category and on-hit effects."""

import pytest
from fastapi import HTTPException

from backend.api.routes.adventures.combat.player_actions import split_weapon_hint
from backend.api.routes.adventures.editing.entity_update.item_metadata import update_weapon
from backend.api.routes.adventures.editing.schemas import EntityUpdateRequest
from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.engine.blueprint.converters import weapon_effects
from backend.engine.combat.weapons import (
    apply_on_hit_effects,
    equipped_weapons,
    normalize_weapon_config,
)
from tests.test_combat_encounters import LETHAL, SESSION_ID, _patch_dice, _play, _seed

VAMPIRE_BLADE = {
    "id": "VAMPIRE_BLADE",
    "name": "Vampire Blade",
    "item_type": "WEAPON",
    "metadata_json": {
        "damage_dice": "1d6",
        "weapon_cost_type": "stamina",
        "weapon_cost_value": 5,
        "weapon_category": "MELEE",
        "weapon_hit_stat": "strength",
        "weapon_effects": [
            {"target": "target", "stat": "stamina", "amount": "-4"},
            {"target": "self", "stat": "hp", "amount": "+3"},
        ],
    },
}


def test_normalize_defaults_to_melee_dexterity_without_effects():
    # Act
    config = normalize_weapon_config({"weapon_hit_stat": "luck", "weapon_effects": "bad"})

    # Assert
    assert config == {"category": "MELEE", "hit_stat": "dexterity", "effects": []}


def test_on_hit_effects_split_between_target_and_wielder():
    # Arrange
    effects = normalize_weapon_config(VAMPIRE_BLADE["metadata_json"])["effects"]
    wielder = {"id": "PLAYER", "name": "Hero", "hp": 50, "max_hp": 60}
    target = {"id": "ORC", "name": "Orc", "stamina": 10, "max_stamina": 10}

    # Act
    applied = apply_on_hit_effects(effects, wielder, target)

    # Assert
    assert target["stamina"] == 6
    assert wielder["hp"] == 53
    assert [(e["entity"], e["stat"], e["delta"]) for e in applied] == [
        ("ORC", "stamina", -4),
        ("PLAYER", "hp", 3),
    ]


def test_editor_update_validates_and_stores_weapon_fields():
    # Arrange
    metadata: dict = {}
    payload = EntityUpdateRequest(
        target_type="object",
        target_id="VAMPIRE_BLADE",
        damage_dice="1d6 + 1",
        weapon_cost_type="mana",
        weapon_cost_value=-3,
        weapon_category="ranged",
        weapon_hit_stat="STRENGTH",
        weapon_effects=[{"target": "self", "stat": "hp", "amount": "+2"}],
    )

    # Act
    update_weapon(metadata, payload, active=True)

    # Assert
    assert metadata == {
        "damage_dice": "1d6+1",
        "weapon_cost_type": "mana",
        "weapon_cost_value": 0,
        "weapon_category": "RANGED",
        "weapon_hit_stat": "strength",
        "weapon_effects": [{"target": "self", "stat": "hp", "amount": "+2"}],
    }


def test_editor_update_rejects_bad_values_and_drops_fields_for_other_types():
    # Arrange
    bad_dice = EntityUpdateRequest(target_type="object", target_id="X", damage_dice="lots")
    bad_effect = EntityUpdateRequest(
        target_type="object", target_id="X", weapon_effects=[{"target": "self", "stat": "hp"}]
    )
    metadata = {"damage_dice": "1d8", "weapon_hit_stat": "strength", "text_log_content": "hi"}

    # Act / Assert
    with pytest.raises(HTTPException):
        update_weapon({}, bad_dice, active=True)
    with pytest.raises(HTTPException):
        update_weapon({}, bad_effect, active=True)
    update_weapon(metadata, EntityUpdateRequest(target_type="object", target_id="X"), False)
    assert metadata == {"text_log_content": "hi"}


def test_blueprint_hit_effects_parse_targets_stats_and_amounts():
    # Act / Assert
    assert weapon_effects("target sta -1d4, self hp +2") == [
        {"target": "target", "stat": "stamina", "amount": "-1d4"},
        {"target": "self", "stat": "hp", "amount": "+2"},
    ]
    with pytest.raises(ValueError):
        weapon_effects("everyone hp -5")


@pytest.mark.asyncio
async def test_player_weapon_uses_hit_stat_and_applies_on_hit_effects(setup_test_db, monkeypatch):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        # Arrange
        user, avatar, _state = await _seed(db)
        avatar.hp = 80
        avatar.equipment = {"MainHand": VAMPIRE_BLADE}
        await db.commit()
        _patch_dice(monkeypatch)
        stats_used: list[str] = []

        def fake_roll(_avatar, hit_stat, _ac, _dice):
            stats_used.append(hit_stat)
            return {**LETHAL, "damage_total": 5, "damage_rolls": [5]}

        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.roll_attack", fake_roll)
        manager = GameTurnManager(db, SESSION_ID, user)
        await _play(manager, "/fight GOBLIN")

        # Act
        await _play(manager, "/attack GOBLIN")

        # Assert
        combat = manager._read_combat_state()
        goblin = next(e for e in combat["enemies"] if e["id"] == "GOBLIN")
        attack = next(
            e for e in combat["log"] if (e.get("data") or {}).get("label") == "Vampire Blade"
        )
        assert stats_used[0] == "strength"
        assert goblin["hp"] == 25
        assert {"entity": "PLAYER", "stat": "hp", "delta": 3} in [
            {k: e[k] for k in ("entity", "stat", "delta")} for e in attack["data"]["effects"]
        ]
        assert "On hit:" in attack["text"]


DAGGER = {
    "id": "DAGGER_OFF",
    "name": "Parrying Dagger",
    "item_type": "WEAPON",
    "metadata_json": {"damage_dice": "1d4", "weapon_cost_value": 2},
}


def test_equipped_weapons_lists_main_hand_first_and_skips_non_weapons():
    # Arrange
    shield = {"id": "SHIELD", "name": "Shield", "item_type": "WEARABLE"}
    equipment = {"OffHand": DAGGER, "MainHand": VAMPIRE_BLADE, "Back": shield}

    # Act
    held = equipped_weapons(equipment)

    # Assert
    assert [(slot, item["id"]) for slot, item in held] == [
        ("MainHand", "VAMPIRE_BLADE"),
        ("OffHand", "DAGGER_OFF"),
    ]
    assert equipped_weapons({"MainHand": VAMPIRE_BLADE, "OffHand": VAMPIRE_BLADE}) == [
        ("MainHand", VAMPIRE_BLADE)
    ]


def test_split_weapon_hint_separates_target_and_weapon():
    # Act / Assert
    assert split_weapon_hint("GOBLIN --with DAGGER_OFF") == ("GOBLIN", "DAGGER_OFF")
    assert split_weapon_hint("GOBLIN") == ("GOBLIN", "")
    assert split_weapon_hint("--with offhand") == ("", "offhand")


@pytest.mark.asyncio
async def test_attack_with_off_hand_weapon_uses_its_profile(setup_test_db, monkeypatch):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        # Arrange
        user, avatar, _state = await _seed(db)
        avatar.equipment = {"MainHand": VAMPIRE_BLADE, "OffHand": DAGGER}
        await db.commit()
        _patch_dice(monkeypatch)
        dice_used: list[str] = []

        def fake_roll(_avatar, _hit_stat, _ac, dice):
            dice_used.append(dice)
            return {**LETHAL, "damage_total": 2, "damage_rolls": [2]}

        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.roll_attack", fake_roll)
        manager = GameTurnManager(db, SESSION_ID, user)
        await _play(manager, "/fight GOBLIN")

        # Act
        await _play(manager, "/attack GOBLIN --with DAGGER_OFF")
        chunks = await _play(manager, "/attack GOBLIN --with Battleaxe")

        # Assert
        combat = manager._read_combat_state()
        labels = [(e.get("data") or {}).get("label") for e in combat["log"]]
        assert dice_used[0] == "1d4"
        assert "Parrying Dagger" in labels
        assert any("no equipped weapon 'Battleaxe'" in chunk for chunk in chunks)
