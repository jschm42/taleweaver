"""The "ally" effect target: abilities that reach the caster's party partner."""

import pytest

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.engine.blueprint import analyze_blueprint
from backend.engine.combat.special_attacks import (
    heals_ally,
    normalize_special_action,
    resolve_special_attack,
)
from backend.engine.combat.weapons import normalize_weapon_config
from backend.engine.party.party_state import PARTY_KEY
from backend.models.world_entity import WorldEntity
from tests.conftest import TestSessionLocal
from tests.test_combat_encounters import SESSION_ID, _patch_dice, _play, _seed

HEALING_WORD = {
    "id": "HEALING_WORD",
    "name": "Healing Word",
    "action_type": "UTILITY",
    "cost": 0,
    "effects": [{"target": "ally", "stat": "hp", "amount": "+10"}],
}


def test_ally_effects_reach_the_partner_only():
    # Arrange
    action = normalize_special_action(HEALING_WORD)
    caster = {"id": "BATLIN", "name": "Batlin", "hp": 20, "max_hp": 20, "mana": 0}
    ally = {"id": "PLAYER", "name": "Alex", "hp": 40, "max_hp": 100}

    # Act
    result = resolve_special_attack(action, caster, None, ally)
    without = resolve_special_attack(action, dict(caster), None)

    # Assert
    assert heals_ally(action) and not action["targets_enemy"]
    assert ally["hp"] == 50 and caster["hp"] == 20
    assert result["effects"][0]["entity"] == "PLAYER"
    assert without["effects"] == []  # no partner: no effect


def test_legacy_heal_can_target_the_ally_and_weapons_cannot():
    # Arrange / Act
    heal = normalize_special_action(
        {"id": "MEND_OTHER", "action_type": "HEAL", "damage_value": "8", "heal_target": "ally"}
    )
    weapon = normalize_weapon_config(
        {"weapon_effects": [{"target": "ally", "stat": "hp", "amount": "+2"}]}
    )

    # Assert
    assert heal["effects"] == [{"target": "ally", "stat": "hp", "amount": "+8"}]
    assert weapon["effects"] == []


def test_blueprint_heals_key_maps_to_heal_target():
    # Arrange
    text = (
        "[Scene: HALL] Hall\n[NPC: LARA] Lara\nin: HALL\n"
        "  [Ability: MEND_OTHER] Mend Other\n  kind: heal\n  damage: 2d6\n  heals: ally\n"
    )

    # Act
    blueprint, _ = analyze_blueprint(text)

    # Assert
    assert blueprint.issues == []
    npc = next(block for block in blueprint.blocks if block.kind == "npc")
    ability = next(child for child in npc.children if child.kind == "ability")
    fields = ability.fields
    assert fields["heal_target"].value == "ally"


@pytest.mark.asyncio
async def test_companion_heals_a_wounded_protagonist_with_an_ally_ability(
    setup_test_db, monkeypatch
):
    async with TestSessionLocal() as db:
        # Arrange: Alex at 30 / 100 HP, Batlin knows Healing Word
        user, avatar, state = await _seed(db)
        db.add(
            WorldEntity(
                id="BATLIN",
                session_id=SESSION_ID,
                entity_type="NPC",
                name="Batlin",
                description="A loyal servant.",
                current_scene_id="ARENA",
                hp=20,
                max_hp=20,
                is_hidden=False,
                is_in_inventory=False,
                metadata_json={
                    "companion": {"tactics": "SUPPORT"},
                    "special_actions": [HEALING_WORD],
                },
            )
        )
        state.entity_states = {PARTY_KEY: {"active_id": "BATLIN", "recruited": ["BATLIN"]}}
        await db.commit()
        _patch_dice(monkeypatch)
        manager = GameTurnManager(db, SESSION_ID, user)
        await _play(manager, "/fight GOBLIN")
        manager.avatar.hp = 30
        combat = manager._read_combat_state()

        # Act
        _ = [c async for c in manager.combat._resolve_companion_turn("BATLIN", combat)]

        # Assert
        assert manager.avatar.hp == 40
        assert combat["log"][-1]["data"]["action_id"] == "HEALING_WORD" or any(
            (e.get("data") or {}).get("action_id") == "HEALING_WORD" for e in combat["log"]
        )
