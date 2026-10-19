"""API tests for PATCH /editor/entity behaviour fixed during the editor decomposition."""

import pytest
from sqlalchemy import select

from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldScene
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _seed() -> str:
    async with TestSessionLocal() as db:
        user = (
            (await db.execute(select(User).where(User.username == "test_user"))).scalars().first()
        )
        adv = AdventureTemplate(
            title="Update", owner_id=user.id, original_manifest={"protagonist": {"name": "Hero"}}
        )
        db.add(adv)
        await db.flush()
        for scene_id in ("HALL", "YARD"):
            db.add(WorldScene(id=scene_id, template_id=adv.id, label=scene_id, description="d"))
        db.add(Avatar(user_id=user.id, template_id=adv.id, name="Hero", stats={}))
        db.add(
            WorldEntity(
                id="GUARD",
                template_id=adv.id,
                entity_type="NPC",
                name="Guard",
                description="Stern.",
                current_scene_id="HALL",
            )
        )
        await db.commit()
        return adv.id


async def test_npc_movement_settings_are_saved(auth_client, setup_test_db):
    # Arrange
    template_id = await _seed()

    # Act
    resp = await auth_client.patch(
        f"/api/adventures/{template_id}/editor/entity",
        json={
            "target_type": "npc",
            "target_id": "GUARD",
            "moveable": True,
            "allowed_scenes": ["HALL", "YARD"],
            "notes": "  patrols at night ",
        },
    )

    # Assert
    assert resp.status_code == 200, resp.text
    async with TestSessionLocal() as db:
        npc = (
            (await db.execute(select(WorldEntity).where(WorldEntity.template_id == template_id)))
            .scalars()
            .one()
        )
    assert npc.moveable is True
    assert npc.movement_type == "MOVABLE"
    assert npc.allowed_scenes == ["HALL", "YARD"]
    assert npc.notes == "patrols at night"


async def test_protagonist_scripts_save_without_inventory(auth_client, setup_test_db):
    # Arrange
    template_id = await _seed()

    # Act
    resp = await auth_client.patch(
        f"/api/adventures/{template_id}/editor/entity",
        json={
            "target_type": "protagonist",
            "target_id": "PROTAGONIST",
            "on_hp_change_script": "  set_flag('hurt', True) ",
        },
    )

    # Assert
    assert resp.status_code == 200, resp.text
    async with TestSessionLocal() as db:
        avatar = (
            (await db.execute(select(Avatar).where(Avatar.template_id == template_id)))
            .scalars()
            .one()
        )
        adv = await db.get(AdventureTemplate, template_id)
    assert avatar.stats["on_hp_change_script"] == "set_flag('hurt', True)"
    assert adv.original_manifest["protagonist"]["on_hp_change_script"] == "set_flag('hurt', True)"
