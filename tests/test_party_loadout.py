"""The companion's loadout: equipment slots, ability switches and their use in combat."""

import pytest

from backend.api.routes.adventures.companion_inventory import GIVE, transfer_companion_items
from backend.api.routes.adventures.companion_loadout import (
    equip_companion,
    toggle_companion_ability,
    unequip_companion,
)
from backend.api.routes.adventures.companion_sheet import build_companion_sheet
from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.engine.party.equipment import (
    carried_equipment,
    choose_slot,
    equip_item,
    equipment_modifiers,
    unequip_slot,
)
from backend.engine.party.party_state import PARTY_KEY, read_party
from backend.models.world_entity import WorldEntity
from tests.conftest import TestSessionLocal
from tests.test_combat_encounters import SESSION_ID as ARENA_SESSION
from tests.test_combat_encounters import _patch_dice, _play, _seed
from tests.test_party_follow import SESSION, _lara, _seed_turn_manager

SPECIALS = [
    {"id": "BITE", "name": "Bite", "effects": [{"target": "target", "stat": "hp", "amount": "-4"}]},
    {
        "id": "SHRIEK",
        "name": "Shriek",
        "effects": [{"target": "target", "stat": "hp", "amount": "-2"}],
    },
]


def _sword(session_id: str, scene: str) -> WorldEntity:
    return WorldEntity(
        id="SWORD",
        session_id=session_id,
        entity_type="OBJECT",
        name="Sword",
        description="A short sword.",
        item_type="WEAPON",
        current_scene_id=scene,
        is_in_inventory=scene == "__INVENTORY__",
        stat_modifier_strength=2,
        metadata_json={"damage_dice": "2d6"},
    )


def test_slot_choice_and_equipment_bookkeeping():
    # Arrange
    states: dict = {"LARA": {"inventory": [{"id": "SWORD"}]}}
    weapon = {"id": "SWORD", "item_type": "WEAPON"}
    helmet = {"id": "HELM", "item_type": "WEARABLE", "wearable_slots": ["Head"]}

    # Act
    equip_item(states, "LARA", "SWORD", choose_slot(weapon, None, {}))
    equipped = dict(carried_equipment(states, "LARA", {"SWORD"}))
    gone = carried_equipment(states, "LARA", set())
    removed = unequip_slot(states, "LARA", "MainHand")

    # Assert
    assert choose_slot(helmet, None, {}) == "Head"
    assert choose_slot(weapon, None, {"MainHand": "AXE"}) == "OffHand"
    assert choose_slot(weapon, "shield", {}) == "OffHand"
    assert equipped == {"MainHand": "SWORD"}
    assert gone == {}  # a slot whose item was given away no longer counts
    assert removed == "SWORD"
    assert (
        equipment_modifiers([{"stat_modifier_strength": 2, "stat_modifier_armor_class": 1}])[
            "armor_class"
        ]
        == 1
    )


def test_ability_switches_survive_the_round_trip():
    # Arrange
    states = {PARTY_KEY: {"active_id": "LARA", "recruited": ["LARA"]}}
    party = read_party(states)

    # Act
    party.set_ability("LARA", "BITE", False)
    reread = read_party({PARTY_KEY: party.to_dict()})

    # Assert
    assert reread.ability_enabled("LARA", "BITE") is False
    assert reread.ability_enabled("LARA", "SHRIEK") is True


@pytest.mark.asyncio
async def test_equip_unequip_and_switch_abilities_from_the_hero_dialog(setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange: the player hands Lara a sword
        manager = await _seed_turn_manager(db)
        db.add(_sword(SESSION, "__INVENTORY__"))
        (await _lara(db)).metadata_json = {"special_actions": SPECIALS}
        manager.avatar.inventory = [{"id": "SWORD", "name": "Sword", "item_type": "WEAPON"}]
        await db.commit()
        await transfer_companion_items(manager, GIVE, "sword")

        # Act
        equipped = await equip_companion(manager, "Sword")
        sheet = await build_companion_sheet(db, manager.state, {})
        unequipped = await unequip_companion(manager, "MainHand")
        switched = await toggle_companion_ability(manager, "BITE off")
        after = await build_companion_sheet(db, manager.state, {})

        # Assert
        assert equipped == [("system", "Lara equips Sword (MainHand).")]
        assert sheet["equipment"]["MainHand"]["id"] == "SWORD"
        assert sheet["inventory"] == []
        assert sheet["stats"]["strength"] == 12  # 10 + 2 from the sword
        assert "takes off SWORD" in unequipped[0][1]
        assert after["equipment"]["MainHand"] is None
        assert [i["id"] for i in after["inventory"]] == ["SWORD"]
        assert switched == [("system", "Lara no longer uses Bite in combat.")]
        assert {a["id"]: a["enabled"] for a in after["abilities"]} == {
            "BITE": False,
            "SHRIEK": True,
        }


@pytest.mark.asyncio
async def test_companion_fights_with_its_equipped_weapon_and_active_abilities(
    setup_test_db, monkeypatch
):
    async with TestSessionLocal() as db:
        # Arrange: Batlin carries and wields a sword; Bite is switched off
        user, _avatar, state = await _seed(db)
        db.add(_sword(ARENA_SESSION, "__INVENTORY__"))
        db.add(
            WorldEntity(
                id="BATLIN",
                session_id=ARENA_SESSION,
                entity_type="NPC",
                name="Batlin",
                description="A loyal servant.",
                current_scene_id="ARENA",
                hp=20,
                max_hp=20,
                is_hidden=False,
                is_in_inventory=False,
                metadata_json={"companion": {"tactics": "BALANCED"}, "special_actions": SPECIALS},
            )
        )
        state.entity_states = {
            PARTY_KEY: {
                "active_id": "BATLIN",
                "recruited": ["BATLIN"],
                "disabled_abilities": {"BATLIN": ["BITE"]},
            },
            "BATLIN": {"inventory": [{"id": "SWORD"}], "equipment": {"MainHand": "SWORD"}},
        }
        await db.commit()
        _patch_dice(monkeypatch)
        manager = GameTurnManager(db, ARENA_SESSION, user)

        # Act
        await _play(manager, "/fight GOBLIN")
        member = manager._read_combat_state()["party"][0]
        batlin = await manager.combat._load_session_entity("BATLIN")
        weapon = await manager.combat._member_weapon(member, batlin)

        # Assert
        assert member["weapon_item_id"] == "SWORD"
        assert weapon["name"] == "Sword" and weapon["dice"] == "2d6"
        assert member["stats"]["strength"] == 12
        assert [a["id"] for a in member["special_actions"]] == ["SHRIEK"]
