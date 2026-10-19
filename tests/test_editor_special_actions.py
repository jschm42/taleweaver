"""API tests for configuring special attacks in the adventure editor."""

import pytest
from sqlalchemy import select

from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.user import User
from backend.models.world_entity import WorldEntity
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio

INSULT = {
    "id": "insult",
    "name": "Insult",
    "description": "Hurts more than a sword.",
    "action_type": "UTILITY",
    "category": "SOCIAL",
    "cost_type": "stamina",
    "cost": 10,
    "effects": [{"target": "target", "stat": "charisma", "amount": "-2"}],
}


async def _seed_template() -> str:
    async with TestSessionLocal() as db:
        user = (
            (await db.execute(select(User).where(User.username == "test_user"))).scalars().first()
        )
        adv = AdventureTemplate(
            title="Specials",
            owner_id=user.id,
            original_manifest={"protagonist": {"name": "Hero"}, "npcs": [{"id": "TROLL"}]},
        )
        db.add(adv)
        await db.flush()
        db.add(Avatar(user_id=user.id, template_id=adv.id, name="Hero", stats={}))
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


async def test_save_protagonist_special_actions(auth_client, setup_test_db):
    # Arrange
    template_id = await _seed_template()

    # Act
    resp = await auth_client.put(
        f"/api/adventures/{template_id}/editor/special-actions",
        json={
            "target_type": "protagonist",
            "target_id": "PROTAGONIST",
            "special_actions": [INSULT],
        },
    )

    # Assert
    assert resp.status_code == 200
    async with TestSessionLocal() as db:
        avatar = (
            (await db.execute(select(Avatar).where(Avatar.template_id == template_id)))
            .scalars()
            .first()
        )
        adv = await db.get(AdventureTemplate, template_id)
        assert avatar.stats["special_actions"][0]["id"] == "INSULT"
        assert avatar.stats["unlocked_actions"] == ["INSULT"]
        assert adv.original_manifest["protagonist"]["special_actions"][0]["cost_type"] == "stamina"


async def test_save_npc_special_actions_keeps_metadata(auth_client, setup_test_db):
    # Arrange
    template_id = await _seed_template()

    # Act
    resp = await auth_client.put(
        f"/api/adventures/{template_id}/editor/special-actions",
        json={"target_type": "npc", "target_id": "TROLL", "special_actions": [INSULT]},
    )

    # Assert
    assert resp.status_code == 200
    async with TestSessionLocal() as db:
        npc = (
            (await db.execute(select(WorldEntity).where(WorldEntity.id == "TROLL")))
            .scalars()
            .first()
        )
        assert npc.metadata_json["attack_mode"] == "PASSIVE"
        assert npc.metadata_json["special_actions"][0]["effects"][0]["stat"] == "charisma"


async def test_rejects_invalid_effect_stat(auth_client, setup_test_db):
    # Arrange
    template_id = await _seed_template()
    bad = {**INSULT, "effects": [{"target": "target", "stat": "luck", "amount": "-2"}]}

    # Act
    resp = await auth_client.put(
        f"/api/adventures/{template_id}/editor/special-actions",
        json={"target_type": "npc", "target_id": "TROLL", "special_actions": [bad]},
    )

    # Assert
    assert resp.status_code == 422
