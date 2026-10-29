"""Export -> import round trip for combat data (special attacks and NPC attack behaviour)."""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from backend.engine.adventures.adventure_exporter import AdventureExporter
from backend.engine.world.world_manifest_applier import apply_manifest
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldScene
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio

SOURCE_ID = "rt-source"
TARGET_ID = "rt-target"
FIREBALL = {
    "id": "FIREBALL",
    "name": "Fireball",
    "action_type": "ATTACK",
    "category": "MAGIC",
    "cost_type": "mana",
    "cost": 25,
    "effects": [{"target": "target", "stat": "hp", "amount": "-3d6"}],
    "is_locked": True,
    "unlock_required_item_id": "TOME",
    "unlock_guard_expression": "tw.vars.get('studied') == True",
    "on_success_script": "tw.vars.set('burned', True)",
}
INSULT = {
    "id": "INSULT",
    "name": "Insult",
    "action_type": "UTILITY",
    "category": "SOCIAL",
    "cost_type": "stamina",
    "cost": 5,
    "effects": [{"target": "target", "stat": "charisma", "amount": "-2"}],
}
NPC_META = {
    "special_actions": [INSULT],
    "attack_mode": "ATTACK_ON_SIGHT",
    "attack_trigger": {"required_item_id": "IDOL", "guard_expression": "tw.player.hp > 0"},
    "special_chance": 70,
    "equipped_weapon_id": "CLUB",
    "on_defeat_text": "The troll collapses.",
}


async def _seed(db) -> User:
    user = (await db.execute(select(User).limit(1))).scalars().first()
    db.add_all(
        [
            AdventureTemplate(
                id=SOURCE_ID, title="Round Trip", owner_id=user.id, rule_enforcement_mode="rpg"
            ),
            AdventureTemplate(
                id=TARGET_ID, title="Round Trip Copy", owner_id=user.id, rule_enforcement_mode="rpg"
            ),
            Avatar(
                user_id=user.id,
                template_id=SOURCE_ID,
                name="Mage",
                hp=80,
                max_hp=80,
                stats={"special_actions": [FIREBALL], "unlocked_actions": []},
            ),  # fmt: skip
            WorldScene(id="CAVE", template_id=SOURCE_ID, label="Cave", description="Damp."),
            WorldEntity(
                id="TROLL",
                template_id=SOURCE_ID,
                entity_type="NPC",
                name="Troll",
                description="Big.",
                current_scene_id="CAVE",
                hp=40,
                max_hp=40,
                metadata_json=dict(NPC_META),
            ),  # fmt: skip
            WorldEntity(
                id="CLUB",
                template_id=SOURCE_ID,
                entity_type="OBJECT",
                name="Club",
                description="Heavy.",
                current_scene_id="INVENTORY",
                item_type="WEAPON",
                is_in_inventory=True,
                metadata_json={"damage_dice": "1d10"},
            ),  # fmt: skip
        ]
    )
    await db.commit()
    return user


async def test_combat_data_survives_export_and_import(auth_client, setup_test_db, monkeypatch):
    monkeypatch.setattr(
        "backend.engine.media.media_engine.MediaEngine.generate_placeholder",
        AsyncMock(return_value="/data/placeholder.svg"),
    )
    async with TestSessionLocal() as db:
        # Arrange
        await _seed(db)
        manifest = await AdventureExporter.build_full_manifest(db, SOURCE_ID)

        # Act
        await apply_manifest(db, TARGET_ID, manifest)

    # Assert
    async with TestSessionLocal() as db:
        avatar = (
            (await db.execute(select(Avatar).where(Avatar.template_id == TARGET_ID)))
            .scalars()
            .first()
        )
        troll = (
            (
                await db.execute(
                    select(WorldEntity).where(
                        WorldEntity.template_id == TARGET_ID, WorldEntity.id == "TROLL"
                    )
                )
            )
            .scalars()
            .first()
        )

        fireball = avatar.stats["special_actions"][0]
        assert fireball["unlock_required_item_id"] == "TOME"
        assert fireball["unlock_guard_expression"] == "tw.vars.get('studied') == True"
        assert fireball["on_success_script"] == "tw.vars.set('burned', True)"
        assert avatar.stats["unlocked_actions"] == []  # locked specials stay locked

        meta = troll.metadata_json
        assert meta["special_actions"][0]["id"] == "INSULT"
        assert meta["attack_mode"] == "ATTACK_ON_SIGHT"
        assert meta["attack_trigger"] == NPC_META["attack_trigger"]
        assert meta["special_chance"] == 70
        assert meta["equipped_weapon_id"] == "CLUB"
        assert meta["on_defeat_text"] == "The troll collapses."
        assert any(item.get("id") == "CLUB" for item in troll.inventory or [])


async def test_generated_npc_fields_are_persisted(auth_client, setup_test_db, monkeypatch):
    monkeypatch.setattr(
        "backend.engine.media.media_engine.MediaEngine.generate_placeholder",
        AsyncMock(return_value="/data/placeholder.svg"),
    )
    manifest = {
        "scenes": [{"id": "HALL", "name": "Hall", "description": "Echoing."}],
        "npcs": [
            {
                "id": "GUARD",
                "name": "Guard",
                "description": "Stern.",
                "special_actions": [INSULT],
                "attack_trigger": {"required_item_id": "IDOL"},
                "special_chance": 55,
            }
        ],
        "protagonist": {"name": "Hero", "special_actions": [FIREBALL, INSULT]},
    }
    async with TestSessionLocal() as db:
        # Arrange
        user = (await db.execute(select(User).limit(1))).scalars().first()
        db.add(
            AdventureTemplate(
                id=TARGET_ID, title="Generated", owner_id=user.id, rule_enforcement_mode="rpg"
            )
        )
        await db.commit()

        # Act
        await apply_manifest(db, TARGET_ID, manifest)

    # Assert
    async with TestSessionLocal() as db:
        guard = (
            (await db.execute(select(WorldEntity).where(WorldEntity.id == "GUARD")))
            .scalars()
            .first()
        )
        avatar = (
            (await db.execute(select(Avatar).where(Avatar.template_id == TARGET_ID)))
            .scalars()
            .first()
        )
        assert guard.metadata_json["attack_trigger"] == {"required_item_id": "IDOL"}
        assert guard.metadata_json["special_chance"] == 55
        assert guard.metadata_json["attack_mode"] == "PASSIVE"
        assert avatar.stats["unlocked_actions"] == ["INSULT"]
