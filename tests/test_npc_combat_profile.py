"""NPC combat profile: configurable main attack, attributes and armor class."""

import io

import pytest
from sqlalchemy import select

from backend.api.routes.adventures.combat.attacks import attack_event_data
from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.engine.blueprint import analyze_blueprint
from backend.engine.blueprint.converters import main_attack
from backend.engine.combat.npc_attack import (
    main_attack_profile,
    normalize_main_attack,
    npc_stat_columns,
)
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldScene
from tests.conftest import TestSessionLocal
from tests.test_combat_encounters import SESSION_ID, _seed

LONGSWORD = {
    "name": "Longsword",
    "category": "MELEE",
    "damage_dice": "1d8+2",
    "hit_stat": "strength",
    "cost_type": "stamina",
    "cost": 4,
    "effects": [{"target": "target", "stat": "stamina", "amount": "-1d4"}],
}


def test_normalize_main_attack_fills_defaults_and_rejects_empty():
    # Act
    sparse = normalize_main_attack({"name": "Bite"})
    junk = normalize_main_attack({"category": "LASER", "damage_dice": "a lot"})

    # Assert
    assert sparse == {
        "name": "Bite",
        "category": "MELEE",
        "damage_dice": "1d6",
        "hit_stat": "dexterity",
        "cost_type": "stamina",
        "cost": 0,
        "effects": [],
    }
    assert junk is None
    assert normalize_main_attack(None) is None


def test_main_attack_profile_matches_the_weapon_profile_shape():
    # Act
    profile = main_attack_profile(LONGSWORD)

    # Assert
    assert profile["dice"] == "1d8+2"
    assert profile["hit_stat"] == "strength"
    assert (profile["cost_type"], profile["cost"]) == ("stamina", 4)
    assert profile["effects"] == [{"target": "target", "stat": "stamina", "amount": "-1d4"}]


def test_npc_stat_columns_prefer_absolute_values_over_stored_columns():
    # Act
    generated = npc_stat_columns({"strength": 15, "armor_class": 17})
    exported = npc_stat_columns({"stat_modifier_dexterity": 12, "stat_modifier_armor_class": 3})

    # Assert
    assert generated["stat_modifier_strength"] == 15
    assert generated["stat_modifier_armor_class"] == 7
    assert generated["stat_modifier_wisdom"] is None
    assert exported["stat_modifier_dexterity"] == 12
    assert exported["stat_modifier_armor_class"] == 3


def test_blueprint_main_attack_converter_reads_all_parts():
    # Act
    attack = main_attack(
        "Magic Missile | 2d4+1 | magic | int | cost: mana 6 | effects: self mana +1"
    )

    # Assert
    assert attack == {
        "name": "Magic Missile",
        "damage_dice": "2d4+1",
        "category": "MAGIC",
        "hit_stat": "intelligence",
        "cost_type": "mana",
        "cost": 6,
        "effects": [{"target": "self", "stat": "mana", "amount": "+1"}],
    }
    with pytest.raises(ValueError):
        main_attack("Bow | far away")


def test_blueprint_npc_stats_and_deprecated_weapon_key():
    # Act
    blueprint, _missing = analyze_blueprint(
        "[Scene: GATE] Gate\nA gate.\n\n"
        "[NPC: ARCHER] Archer\nin: GATE\ndex: 16\nac: 13\n"
        "main_attack: Longbow | 1d8 | ranged | dex\nweapon: OLD_BOW\n\n"
        "[Item: OLD_BOW] Old Bow\nin: GATE\n"
    )

    # Assert
    fixed = blueprint.first("npc").fixed()
    assert (fixed["dexterity"], fixed["armor_class"]) == (16, 13)
    assert fixed["main_attack"]["category"] == "RANGED"
    warnings = [issue.message for issue in blueprint.issues if issue.severity == "warning"]
    assert any("'weapon' is deprecated" in w for w in warnings)


async def _goblin_entity(db, **meta) -> WorldEntity:
    res = await db.execute(
        select(WorldEntity).where(WorldEntity.session_id == SESSION_ID, WorldEntity.id == "GOBLIN")
    )
    goblin = res.scalars().first()
    goblin.metadata_json = {**(goblin.metadata_json or {}), **meta}
    goblin.stat_modifier_strength = 15
    goblin.stat_modifier_armor_class = 6
    await db.commit()
    return goblin


@pytest.mark.asyncio
async def test_enemy_uses_main_attack_before_the_deprecated_weapon_item(setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange
        user, _avatar, _state = await _seed(db)
        db.add(
            WorldEntity(
                id="RUSTY_AXE",
                session_id=SESSION_ID,
                entity_type="OBJECT",
                name="Rusty Axe",
                description="Old.",
                current_scene_id="INVENTORY",
                item_type="WEAPON",
                metadata_json={"damage_dice": "1d12"},
            )
        )
        goblin = await _goblin_entity(db, equipped_weapon_id="RUSTY_AXE")
        manager = GameTurnManager(db, SESSION_ID, user)
        await manager.initialize()

        # Act
        legacy = await manager.combat._enemy_weapon_profile(goblin)
        goblin = await _goblin_entity(db, main_attack=LONGSWORD)
        configured = await manager.combat._enemy_weapon_profile(goblin)
        entry = await manager.combat._build_enemy_entry(goblin, engaged=True)

        # Assert
        assert (legacy["name"], legacy["dice"]) == ("Rusty Axe", "1d12")
        assert (configured["name"], configured["dice"]) == ("Longsword", "1d8+2")
        assert configured["hit_stat"] == "strength"
        assert entry["ac"] == 16
        assert entry["stats"]["strength"] == 15


# --- Editor API ------------------------------------------------------------------------


async def _seed_template() -> str:
    async with TestSessionLocal() as db:
        user = (
            (await db.execute(select(User).where(User.username == "test_user"))).scalars().first()
        )
        adv = AdventureTemplate(
            title="Profiles",
            owner_id=user.id,
            original_manifest={"npcs": [{"id": "TROLL", "stat_modifier_armor_class": 0}]},
        )
        db.add(adv)
        await db.flush()
        db.add(WorldScene(id="CAVE", template_id=adv.id, label="Cave", description="Dark."))
        db.add(
            WorldEntity(
                id="TROLL",
                template_id=adv.id,
                entity_type="NPC",
                name="Troll",
                description="Big.",
                current_scene_id="CAVE",
                metadata_json={"attack_mode": "PASSIVE"},
            )
        )
        await db.commit()
        return adv.id


async def _troll(template_id: str) -> WorldEntity:
    async with TestSessionLocal() as db:
        res = await db.execute(
            select(WorldEntity).where(
                WorldEntity.template_id == template_id, WorldEntity.id == "TROLL"
            )
        )
        return res.scalars().first()


@pytest.mark.asyncio
async def test_editor_saves_npc_profile_on_entity_and_manifest(auth_client, setup_test_db):
    # Arrange
    template_id = await _seed_template()

    # Act
    resp = await auth_client.put(
        f"/api/adventures/{template_id}/editor/npc-profile",
        json={
            "npc_id": "TROLL",
            "strength": 18,
            "dexterity": 8,
            "armor_class": 15,
            "main_attack": {"name": "Club", "damage_dice": "2D6 + 1", "hit_stat": "strength"},
        },
    )

    # Assert
    assert resp.status_code == 200
    troll = await _troll(template_id)
    assert (troll.stat_modifier_strength, troll.stat_modifier_dexterity) == (18, 8)
    assert troll.stat_modifier_armor_class == 5
    assert troll.metadata_json["main_attack"]["damage_dice"] == "2d6+1"
    assert troll.metadata_json["attack_mode"] == "PASSIVE"
    async with TestSessionLocal() as db:
        manifest_npc = (await db.get(AdventureTemplate, template_id)).original_manifest["npcs"][0]
    assert (manifest_npc["armor_class"], manifest_npc["stat_modifier_armor_class"]) == (15, 5)
    assert manifest_npc["main_attack"]["name"] == "Club"


@pytest.mark.asyncio
async def test_editor_rejects_bad_dice_and_out_of_range_stats(auth_client, setup_test_db):
    # Arrange
    template_id = await _seed_template()
    url = f"/api/adventures/{template_id}/editor/npc-profile"

    # Act
    bad_dice = await auth_client.put(
        url, json={"npc_id": "TROLL", "main_attack": {"name": "Club", "damage_dice": "lots"}}
    )
    too_strong = await auth_client.put(url, json={"npc_id": "TROLL", "strength": 99})

    # Assert
    assert bad_dice.status_code == 400
    assert too_strong.status_code == 422


@pytest.mark.asyncio
async def test_npc_bundle_round_trip_keeps_combat_profile(auth_client, setup_test_db):
    # Arrange
    template_id = await _seed_template()
    await auth_client.put(
        f"/api/adventures/{template_id}/editor/npc-profile",
        json={"npc_id": "TROLL", "wisdom": 4, "armor_class": 12, "main_attack": LONGSWORD},
    )

    # Act
    exported = await auth_client.get(f"/api/adventures/{template_id}/editor/transfer/entity/TROLL")
    imported = await auth_client.post(
        f"/api/adventures/{template_id}/editor/transfer/import",
        data={"expected_kind": "npc"},
        files={"file": ("troll.twe", io.BytesIO(exported.content), "application/zip")},
    )

    # Assert
    assert exported.status_code == 200
    assert imported.status_code == 200
    copy_id = imported.json()["entity_id"]
    async with TestSessionLocal() as db:
        res = await db.execute(
            select(WorldEntity).where(
                WorldEntity.template_id == template_id, WorldEntity.id == copy_id
            )
        )
        copy = res.scalars().first()
    assert copy_id != "TROLL"
    assert (copy.stat_modifier_wisdom, copy.stat_modifier_armor_class) == (4, 2)
    assert copy.metadata_json["main_attack"]["name"] == "Longsword"


@pytest.mark.asyncio
async def test_duplicating_an_npc_keeps_its_combat_profile(auth_client, setup_test_db):
    # Arrange
    template_id = await _seed_template()
    await auth_client.put(
        f"/api/adventures/{template_id}/editor/npc-profile",
        json={"npc_id": "TROLL", "strength": 17, "main_attack": LONGSWORD},
    )

    # Act
    resp = await auth_client.post(f"/api/adventures/{template_id}/editor/entity/TROLL/clone")

    # Assert
    assert resp.status_code == 200
    assert resp.json()["new_id"] == "TROLL_1"
    async with TestSessionLocal() as db:
        res = await db.execute(
            select(WorldEntity).where(
                WorldEntity.template_id == template_id, WorldEntity.id == "TROLL_1"
            )
        )
        clone = res.scalars().first()
    assert clone.stat_modifier_strength == 17
    assert clone.metadata_json["main_attack"]["damage_dice"] == "1d8+2"


def test_world_builder_prompt_explains_combat_profile_and_talents():
    # Arrange
    from backend.engine.world.world_prompt_builder import (
        _build_special_attack_requirement,
        _build_talent_requirement,
    )

    # Act
    combat = _build_special_attack_requirement(True, True)
    talents = _build_talent_requirement()

    # Assert
    assert "NPC COMBAT PROFILE" in combat and "main_attack" in combat
    assert "deprecated" in combat
    assert talents.startswith("\n\nPROTAGONIST TALENTS")


def test_attack_event_carries_the_weapon_category_for_the_arena():
    # Arrange
    roll = {"hit_roll": 14, "hit_modifier": 2, "hit_total": 16, "is_hit": True, "is_crit": False}
    actor = {"id": "ORC", "name": "Orc"}
    target = {"id": "PLAYER", "name": "Hero"}

    # Act
    ranged = attack_event_data(actor, target, roll, 12, "Shortbow", 5, "RANGED")
    default = attack_event_data(actor, target, roll, 12, "Club", 5)
    junk = attack_event_data(actor, target, roll, 12, "Club", 5, "LASER")

    # Assert
    assert ranged["category"] == "RANGED"
    assert default["category"] == "MELEE"
    assert junk["category"] == "MELEE"
