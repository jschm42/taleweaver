"""Running the validator must not change the adventure it inspects."""

import pytest
from sqlalchemy import select

from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldScene
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def test_validation_keeps_protagonist_inventory_as_id_list(auth_client, setup_test_db):
    # Arrange
    async with TestSessionLocal() as db:
        user = (
            (await db.execute(select(User).where(User.username == "test_user"))).scalars().first()
        )
        adv = AdventureTemplate(title="Side effects", owner_id=user.id)
        db.add(adv)
        await db.flush()
        db.add(WorldScene(id="START", template_id=adv.id, label="Start", description="Room."))
        db.add(
            WorldEntity(
                id="SWORD",
                template_id=adv.id,
                entity_type="OBJECT",
                name="Sword",
                description="Sharp.",
                current_scene_id="INVENTORY",
                is_in_inventory=True,
            )
        )
        db.add(
            Avatar(
                user_id=user.id,
                template_id=adv.id,
                name="Hero",
                inventory=["SWORD"],
                equipment={"MainHand": "SWORD"},
            )
        )
        await db.commit()
        template_id = adv.id

    # Act
    resp = await auth_client.post(
        f"/api/adventures/{template_id}/editor/validate", json={"include_ai": False}
    )

    # Assert
    assert resp.status_code == 200, resp.text
    async with TestSessionLocal() as db:
        avatar = (
            (await db.execute(select(Avatar).where(Avatar.template_id == template_id)))
            .scalars()
            .one()
        )
    assert avatar.inventory == ["SWORD"]
    assert avatar.equipment == {"MainHand": "SWORD"}
    codes = {f["code"] for f in resp.json()["structural_findings"]}
    assert "protagonist_item_missing" not in codes
