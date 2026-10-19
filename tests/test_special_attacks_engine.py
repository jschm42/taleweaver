"""Unit tests for the pure special attack and initiative rules."""

from backend.engine.combat.initiative import PLAYER_ID, roll_initiative
from backend.engine.combat.special_attacks import (
    describe_special_result,
    normalize_special_action,
    resolve_special_attack,
    roll_amount,
)


def _combatant(cid: str, **overrides):
    base = {
        "id": cid,
        "name": cid.title(),
        "hp": 50,
        "max_hp": 50,
        "mana": 40,
        "max_mana": 40,
        "stamina": 30,
        "max_stamina": 30,
        "stats": {
            "strength": 10,
            "dexterity": 10,
            "intelligence": 14,
            "wisdom": 10,
            "charisma": 16,
        },
        "ac": 12,
        "modifiers": {},
    }
    base.update(overrides)
    return base


def test_legacy_attack_maps_to_target_hp_effect():
    # Arrange
    raw = {
        "id": "FIREBALL",
        "name": "Fireball",
        "action_type": "ATTACK",
        "mana_cost": 25,
        "damage_type": "ROLLED",
        "damage_value": "3d6",
    }

    # Act
    action = normalize_special_action(raw)

    # Assert
    assert action["cost_type"] == "mana"
    assert action["cost"] == 25
    assert action["effects"] == [{"target": "target", "stat": "hp", "amount": "-3d6"}]
    assert action["targets_enemy"] is True


def test_legacy_heal_is_self_effect_without_roll(monkeypatch):
    # Arrange
    action = normalize_special_action(
        {
            "id": "HEAL",
            "name": "Heal",
            "action_type": "HEAL",
            "mana_cost": 10,
            "damage_type": "FIXED",
            "damage_value": "15",
        }
    )
    caster = _combatant("hero", hp=20)

    # Act
    result = resolve_special_attack(action, caster, None)

    # Assert
    assert result["rolled"] is False
    assert caster["hp"] == 35
    assert caster["mana"] == 30


def test_insult_drains_target_charisma_and_costs_stamina(monkeypatch):
    # Arrange
    action = normalize_special_action(
        {
            "id": "INSULT",
            "name": "Vicious Insult",
            "action_type": "UTILITY",
            "category": "SOCIAL",
            "cost_type": "stamina",
            "cost": 10,
            "difficulty": 12,
            "effects": [
                {"target": "target", "stat": "charisma", "amount": "-3"},
                {"target": "target", "stat": "hp", "amount": "-2"},
                {"target": "self", "stat": "strength", "amount": "+2"},
            ],
        }
    )
    caster = _combatant("hero")
    target = _combatant("troll")
    monkeypatch.setattr("backend.engine.combat.special_attacks.random.randint", lambda *_a: 15)

    # Act
    result = resolve_special_attack(action, caster, target)

    # Assert
    assert action["success_stat"] == "charisma"
    assert result["success"] is True
    assert result["total"] == 15 + 3
    assert caster["stamina"] == 20
    assert target["modifiers"]["charisma"] == -3
    assert target["hp"] == 48
    assert caster["modifiers"]["strength"] == 2
    assert "Vicious Insult on Troll" in describe_special_result("Hero", "Troll", result)


def test_failed_roll_pays_cost_without_effects(monkeypatch):
    # Arrange
    action = normalize_special_action(
        {
            "id": "SMITE",
            "name": "Smite",
            "action_type": "ATTACK",
            "category": "MELEE",
            "cost_type": "stamina",
            "cost": 5,
            "effects": [{"target": "target", "stat": "hp", "amount": "-10"}],
        }
    )
    caster = _combatant("hero")
    target = _combatant("troll", ac=30)
    monkeypatch.setattr("backend.engine.combat.special_attacks.random.randint", lambda *_a: 5)

    # Act
    result = resolve_special_attack(action, caster, target)

    # Assert
    assert result["success"] is False
    assert result["dc"] == 30
    assert target["hp"] == 50
    assert caster["stamina"] == 25


def test_critical_success_doubles_target_effects(monkeypatch):
    # Arrange
    action = normalize_special_action(
        {
            "id": "BOLT",
            "name": "Bolt",
            "action_type": "ATTACK",
            "effects": [{"target": "target", "stat": "hp", "amount": "-6"}],
        }
    )
    target = _combatant("troll")
    monkeypatch.setattr("backend.engine.combat.special_attacks.random.randint", lambda *_a: 20)

    # Act
    result = resolve_special_attack(action, _combatant("hero"), target)

    # Assert
    assert result["crit"] is True
    assert target["hp"] == 38


def test_invalid_effects_are_dropped_and_amounts_parse():
    # Arrange / Act
    action = normalize_special_action(
        {
            "id": "ODD",
            "action_type": "UTILITY",
            "effects": [{"stat": "luck", "amount": "-1"}, {"stat": "hp", "amount": "lots"}],
        }
    )

    # Assert
    assert action["effects"] == []
    assert roll_amount("+5") == (5, "5")
    assert roll_amount("-3")[0] == -3


def test_initiative_orders_by_total_and_prefers_player_on_ties(monkeypatch):
    # Arrange
    monkeypatch.setattr("backend.engine.combat.initiative.random.randint", lambda *_a: 10)
    participants = [
        {"id": PLAYER_ID, "name": "Hero", "dexterity": 4},
        {"id": "RAT", "name": "Rat", "dexterity": 4},
        {"id": "OGRE", "name": "Ogre", "dexterity": 8},
    ]

    # Act
    order = roll_initiative(participants)

    # Assert
    assert [e["id"] for e in order] == ["OGRE", PLAYER_ID, "RAT"]
