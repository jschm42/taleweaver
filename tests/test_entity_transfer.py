"""API tests for exporting/importing single NPCs, items, and the protagonist (.twe bundles)."""

import io
import os
import zipfile

import pytest
from PIL import Image
from sqlalchemy import select

from backend.core.config import settings
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldScene
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


def _png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), (200, 30, 30)).save(buffer, format="PNG")
    return buffer.getvalue()


def _write_image(template_id: str, name: str) -> str:
    rel = f"adventures/library/{template_id}/visuals/{name}.png"
    path = os.path.join(settings.DATA_DIR, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(_png_bytes())
    return f"/data/{rel}"


async def _seed_template(title: str, scene_id: str, *, with_entities: bool) -> str:
    async with TestSessionLocal() as db:
        user = (
            (await db.execute(select(User).where(User.username == "test_user"))).scalars().first()
        )
        adv = AdventureTemplate(
            title=title, owner_id=user.id, original_manifest={"protagonist": {"name": "Hero"}}
        )
        db.add(adv)
        await db.flush()
        db.add(WorldScene(id=scene_id, template_id=adv.id, label=scene_id, description="Room."))
        db.add(
            Avatar(
                user_id=user.id,
                template_id=adv.id,
                name="Hero",
                strength=12,
                stats={"special_actions": [{"id": "INSULT"}]},
                inventory=["SWORD"],
                profile_image=_write_image(adv.id, "hero") if with_entities else None,
            )
        )
        if with_entities:
            db.add(
                WorldEntity(
                    id="TROLL",
                    template_id=adv.id,
                    entity_type="NPC",
                    name="Troll",
                    description="Big and green.",
                    current_scene_id=scene_id,
                    image_url=_write_image(adv.id, "troll"),
                    hp=80,
                    inventory=["SWORD"],
                    allowed_scenes=[scene_id],
                    metadata_json={"attack_mode": "ATTACK_ON_SIGHT"},
                )
            )
            db.add(
                WorldEntity(
                    id="SWORD",
                    template_id=adv.id,
                    entity_type="OBJECT",
                    name="Sword",
                    description="Sharp.",
                    current_scene_id=scene_id,
                    item_type="WEAPON",
                    stat_modifier_strength=3,
                )
            )
        await db.commit()
        return adv.id


@pytest.fixture
def data_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path / "data"))


async def _import(auth_client, template_id: str, content: bytes, kind: str | None = None):
    data = {"expected_kind": kind} if kind else {}
    return await auth_client.post(
        f"/api/adventures/{template_id}/editor/transfer/import",
        data=data,
        files={"file": ("bundle.twe", content, "application/zip")},
    )


async def test_npc_round_trip_into_other_adventure(auth_client, setup_test_db, data_dir):
    # Arrange
    source_id = await _seed_template("Source", "CAVE", with_entities=True)
    target_id = await _seed_template("Target", "HALL", with_entities=False)

    # Act
    export = await auth_client.get(f"/api/adventures/{source_id}/editor/transfer/entity/TROLL")
    resp = await _import(auth_client, target_id, export.content, "npc")

    # Assert
    assert export.status_code == 200
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["entity_id"] == "TROLL"
    assert body["has_image"] is True
    async with TestSessionLocal() as db:
        npc = (
            (await db.execute(select(WorldEntity).where(WorldEntity.template_id == target_id)))
            .scalars()
            .one()
        )
    assert npc.entity_type == "NPC"
    assert npc.hp == 80
    assert npc.current_scene_id == "HALL"
    assert npc.inventory == []
    assert npc.allowed_scenes == []
    assert npc.metadata_json["attack_mode"] == "ATTACK_ON_SIGHT"
    assert npc.image_url.startswith(f"/data/adventures/library/{target_id}/visuals/npc/")
    assert len(body["warnings"]) == 3


async def test_item_import_into_same_adventure_gets_new_id(auth_client, setup_test_db, data_dir):
    # Arrange
    template_id = await _seed_template("Source", "CAVE", with_entities=True)
    export = await auth_client.get(f"/api/adventures/{template_id}/editor/transfer/entity/SWORD")

    # Act
    resp = await _import(auth_client, template_id, export.content, "item")

    # Assert
    assert resp.status_code == 200, resp.text
    assert resp.json()["entity_id"] == "SWORD_2"
    async with TestSessionLocal() as db:
        res = await db.execute(
            select(WorldEntity).where(
                WorldEntity.template_id == template_id, WorldEntity.id == "SWORD_2"
            )
        )
        item = res.scalars().one()
    assert item.item_type == "WEAPON"
    assert item.stat_modifier_strength == 3
    assert item.current_scene_id == "CAVE"
    assert item.image_url is None


async def test_protagonist_import_replaces_profile_but_keeps_inventory(
    auth_client, setup_test_db, data_dir
):
    # Arrange
    source_id = await _seed_template("Source", "CAVE", with_entities=True)
    target_id = await _seed_template("Target", "HALL", with_entities=False)
    async with TestSessionLocal() as db:
        avatar = (
            (await db.execute(select(Avatar).where(Avatar.template_id == source_id)))
            .scalars()
            .one()
        )
        avatar.name = "Aria"
        avatar.strength = 17
        await db.commit()

    # Act
    export = await auth_client.get(f"/api/adventures/{source_id}/editor/transfer/protagonist")
    resp = await _import(auth_client, target_id, export.content, "protagonist")

    # Assert
    assert resp.status_code == 200, resp.text
    async with TestSessionLocal() as db:
        avatar = (
            (await db.execute(select(Avatar).where(Avatar.template_id == target_id)))
            .scalars()
            .one()
        )
        adv = await db.get(AdventureTemplate, target_id)
    assert avatar.name == "Aria"
    assert avatar.strength == 17
    assert avatar.inventory == ["SWORD"]
    assert avatar.profile_image.startswith(f"/data/adventures/library/{target_id}/")
    assert adv.original_manifest["protagonist"]["name"] == "Aria"
    assert adv.original_manifest["protagonist"]["special_actions"] == [{"id": "INSULT"}]


async def test_import_rejects_kind_mismatch(auth_client, setup_test_db, data_dir):
    # Arrange
    template_id = await _seed_template("Source", "CAVE", with_entities=True)
    export = await auth_client.get(f"/api/adventures/{template_id}/editor/transfer/entity/TROLL")

    # Act
    resp = await _import(auth_client, template_id, export.content, "item")

    # Assert
    assert resp.status_code == 400
    assert "npc" in resp.json()["detail"]


async def test_import_rejects_invalid_files(auth_client, setup_test_db, data_dir):
    # Arrange
    template_id = await _seed_template("Source", "CAVE", with_entities=True)
    foreign_zip = io.BytesIO()
    with zipfile.ZipFile(foreign_zip, "w") as zip_file:
        zip_file.writestr("adventure.adv", "{}")

    # Act
    not_zip = await _import(auth_client, template_id, b"not a zip")
    wrong_zip = await _import(auth_client, template_id, foreign_zip.getvalue())

    # Assert
    assert not_zip.status_code == 400
    assert wrong_zip.status_code == 400
    assert "entity.json" in wrong_zip.json()["detail"]
