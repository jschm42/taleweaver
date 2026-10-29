"""Tests for area-of-effect special attacks (splash / all enemies, saving throws)."""

import pytest

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.engine.blueprint.converters import ability_area
from backend.engine.combat.area_attacks import (
    describe_area_result,
    is_area_attack,
    resolve_area_attack,
    select_area_targets,
)
from backend.engine.combat.special_attacks import normalize_special_action
from tests.test_combat_encounters import SESSION_ID, _patch_dice, _play, _seed
from tests.test_special_attacks_engine import _combatant

FIREBALL = {
    "id": "FIREBALL",
    "name": "Fireball",
    "category": "MAGIC",
    "cost_type": "mana",
    "cost": 12,
    "difficulty": 13,
    "target_scope": "ALL_ENEMIES",
    "save_stat": "dexterity",
    "effects": [{"target": "target", "stat": "hp", "amount": "-10"}],
}


def _enemy(eid: str, engaged: bool = True, dex: int = 10):
    base = _combatant(eid, engaged=engaged)
    base["stats"]["dexterity"] = dex
    return base


def _fix_rolls(monkeypatch, *values):
    rolls = iter(values)
    monkeypatch.setattr(
        "backend.engine.combat.area_attacks.random.randint", lambda *_a: next(rolls)
    )


def test_normalize_keeps_area_fields_and_defaults_to_single():
    # Arrange / Act
    area = normalize_special_action({**FIREBALL, "splash_radius": 9, "save_stat": "luck"})
    plain = normalize_special_action({"id": "JAB", "name": "Jab"})

    # Assert
    assert area["target_scope"] == "ALL_ENEMIES"
    assert area["splash_radius"] == 2
    assert area["save_stat"] is None
    assert plain["target_scope"] == "SINGLE"
    assert is_area_attack(area) is True
    assert is_area_attack(plain) is False


def test_select_targets_respects_scope_radius_and_passive_flag():
    # Arrange
    enemies = [_enemy("A"), _enemy("B"), _enemy("C", engaged=False), _enemy("D"), _enemy("E")]
    all_enemies = normalize_special_action(FIREBALL)
    sparing = normalize_special_action({**FIREBALL, "spares_passive": True})
    splash = {**all_enemies, "target_scope": "SPLASH", "splash_radius": 1}
    sparing_splash = {**splash, "spares_passive": True}

    # Act
    hit_all = [t["id"] for t in select_area_targets(all_enemies, enemies, "A")]
    hit_sparing = [t["id"] for t in select_area_targets(sparing, enemies, "A")]
    hit_splash = [t["id"] for t in select_area_targets(splash, enemies, "D")]
    hit_sparing_splash = [t["id"] for t in select_area_targets(sparing_splash, enemies, "D")]

    # Assert
    assert hit_all == ["A", "B", "C", "D", "E"]
    assert hit_sparing == ["A", "B", "D", "E"]
    assert hit_splash == ["C", "D", "E"]
    assert hit_sparing_splash == ["B", "D", "E"]


def test_saving_throw_halves_damage_for_targets_that_save(monkeypatch):
    # Arrange
    attack = normalize_special_action(FIREBALL)
    caster = _combatant("PLAYER")
    failer, saver = _enemy("ORC"), _enemy("ELF", dex=16)
    _fix_rolls(monkeypatch, 5, 12)  # ORC: 5 + 0 = 5 fails; ELF: 12 + 3 = 15 saves

    # Act
    result = resolve_area_attack(attack, caster, [failer, saver], "ORC")

    # Assert
    assert caster["mana"] == 28
    assert failer["hp"] == 40
    assert saver["hp"] == 45
    assert [t["save"]["success"] for t in result["targets"]] == [False, True]
    text = describe_area_result("Hero", result)
    assert "Orc fails the Dexterity save (5 vs DC 13): Orc HP -10" in text
    assert "Elf makes the Dexterity save (15 vs DC 13): Elf HP -5" in text


def test_attack_roll_is_compared_against_each_target_ac(monkeypatch):
    # Arrange
    attack = normalize_special_action(
        {**FIREBALL, "save_stat": None, "difficulty": None, "target_scope": "SPLASH"}
    )
    caster = _combatant("PLAYER")  # INT 14 -> +2
    near = _enemy("NEAR")
    armored = _enemy("TANK")
    armored["ac"] = 18
    _fix_rolls(monkeypatch, 11)  # 11 + 2 = 13 hits AC 12, misses AC 18

    # Act
    result = resolve_area_attack(attack, caster, [near, armored], "NEAR")

    # Assert
    assert result["rolled"] is True
    assert result["dc"] == 12
    assert near["hp"] == 40
    assert armored["hp"] == 50
    assert [t["hit"] for t in result["targets"]] == [True, False]


def test_splash_neighbours_take_half(monkeypatch):
    # Arrange
    attack = normalize_special_action({**FIREBALL, "target_scope": "SPLASH"})
    caster = _combatant("PLAYER")
    primary, neighbour = _enemy("A"), _enemy("B")
    _fix_rolls(monkeypatch, 2, 2)  # both fail the save

    # Act
    resolve_area_attack(attack, caster, [primary, neighbour], "A")

    # Assert
    assert primary["hp"] == 40
    assert neighbour["hp"] == 45


def test_blueprint_area_key_parses_scope_and_radius():
    # Act / Assert
    assert ability_area("all") == {"target_scope": "ALL_ENEMIES"}
    assert ability_area("splash 2") == {"target_scope": "SPLASH", "splash_radius": 2}
    with pytest.raises(ValueError):
        ability_area("all 2")
    with pytest.raises(ValueError):
        ability_area("cone")


@pytest.mark.asyncio
async def test_player_fireball_hits_every_enemy_and_engages_passive_ones(
    setup_test_db, monkeypatch
):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        # Arrange
        user, _avatar, _state = await _seed(
            # Abilities saved before the opt-out still carry the old opt-in key; it is ignored.
            db,
            special_actions=[{**FIREBALL, "hits_passive": False}],
        )
        _patch_dice(monkeypatch)
        # A natural 1 fails every save (random is shared, so initiative rolls 1 as well).
        monkeypatch.setattr("backend.engine.combat.area_attacks.random.randint", lambda *_a: 1)
        manager = GameTurnManager(db, SESSION_ID, user)
        await _play(manager, "/fight GOBLIN")

        # Act
        await _play(manager, "/special FIREBALL")

        # Assert
        combat = manager._read_combat_state()
        hp = {e["id"]: e["hp"] for e in combat["enemies"]}
        assert hp == {"GOBLIN": 20, "ORC": 20}
        assert all(e["engaged"] for e in combat["enemies"])
        special = next(e for e in combat["log"] if (e.get("data") or {}).get("scope"))
        assert {t["id"] for t in special["data"]["targets"]} == {"GOBLIN", "ORC"}
