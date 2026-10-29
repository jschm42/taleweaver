import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.routes.adventures.editing.entity_update.loadout import resolve_loadout
from backend.core.auth import create_access_token
from backend.core.database import get_db
from backend.main import app
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.user import User
from backend.models.world_entity import WorldEntity
from tests.conftest import TestSessionLocal


async def override_get_db():
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture
async def client():
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


def test_equipping_a_packed_item_removes_it_from_inventory():
    # Arrange
    old_inventory = ["VIAL", "SWORD"]
    old_equipment = {"MainHand": None}

    # Act
    inventory, equipment = resolve_loadout(
        old_inventory, old_equipment, ["VIAL", "SWORD"], {"MainHand": "SWORD"}
    )

    # Assert
    assert inventory == ["VIAL"]
    assert equipment == {"MainHand": "SWORD"}


def test_packing_an_equipped_item_unequips_it():
    # Arrange
    old_inventory = ["VIAL"]
    old_equipment = {"MainHand": "SWORD"}

    # Act
    inventory, equipment = resolve_loadout(
        old_inventory, old_equipment, ["VIAL", "SWORD"], {"MainHand": "SWORD"}
    )

    # Assert
    assert inventory == ["VIAL", "SWORD"]
    assert equipment == {"MainHand": None}


def test_moving_an_item_to_another_slot_clears_the_old_slot():
    # Arrange
    old_equipment = {"Ring_1": "RING", "Ring_2": None}

    # Act
    _, equipment = resolve_loadout([], old_equipment, [], {"Ring_1": "RING", "Ring_2": "RING"})

    # Assert
    assert equipment == {"Ring_1": None, "Ring_2": "RING"}


def test_stored_duplicates_keep_the_equipment_slot():
    # Arrange
    stored_inventory = [{"id": "SWORD", "name": "Practice Sword"}, "VIAL"]
    stored_equipment = {"MainHand": "SWORD"}

    # Act
    inventory, equipment = resolve_loadout(
        stored_inventory, stored_equipment, list(stored_inventory), dict(stored_equipment)
    )

    # Assert
    assert inventory == ["VIAL"]
    assert equipment == {"MainHand": "SWORD"}


@pytest.mark.asyncio
async def test_editor_equip_removes_item_from_starting_inventory(client, setup_test_db):
    # Arrange
    async with TestSessionLocal() as db:
        user = User(username="loadout_user", hashed_password="x", role="admin")
        db.add(user)
        await db.flush()
        template = AdventureTemplate(
            title="Loadout",
            owner_id=user.id,
            version="2.0.0",
            is_ready=True,
            creation_status="Ready",
            original_manifest={
                "version": "2.0.0",
                "protagonist": {"name": "Hero", "starting_inventory": ["VIAL", "SWORD"]},
            },
        )
        db.add(template)
        await db.flush()
        avatar = Avatar(
            user_id=user.id, template_id=template.id, name="Hero", inventory=["VIAL", "SWORD"]
        )
        db.add(avatar)
        for item_id in ("VIAL", "SWORD"):
            db.add(
                WorldEntity(
                    id=item_id,
                    template_id=template.id,
                    entity_type="OBJECT",
                    name=item_id.title(),
                    description="An item.",
                    current_scene_id="INVENTORY",
                    is_in_inventory=True,
                )
            )
        await db.commit()
        template_id, avatar_id = template.id, avatar.id

    token = create_access_token(data={"sub": "loadout_user"})

    # Act: the editor always sends both lists, unchanged inventory plus the new slot
    res = await client.patch(
        f"/api/adventures/{template_id}/editor/entity",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "target_type": "protagonist",
            "target_id": avatar_id,
            "inventory": ["VIAL", "SWORD"],
            "equipment": {"MainHand": "SWORD"},
        },
    )

    # Assert
    assert res.status_code == 200, res.text
    async with TestSessionLocal() as db:
        av = await db.get(Avatar, avatar_id)
        adv = await db.get(AdventureTemplate, template_id)
        assert av.inventory == ["VIAL"]
        assert av.equipment["MainHand"] == "SWORD"
        assert adv.original_manifest["protagonist"]["starting_inventory"] == ["VIAL"]
