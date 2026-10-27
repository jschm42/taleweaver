"""Retain usable visual assets for adventures created with legacy Unicode IDs."""

from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import select

from backend.core.config import settings
from backend.engine.manifest_apply.assets import copy_source_asset_to_current_adventure
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.models.world_entity import WorldScene
from backend.utils.path_security import data_url_to_local_path
from tests.conftest import TestSessionLocal

LEGACY_ID = "одинокий-путник-ab12cd34"


@pytest.fixture
async def legacy_world(auth_client, tmp_path, monkeypatch):
    data = tmp_path / "Данные игры"
    monkeypatch.setattr(settings, "DATA_DIR", str(data))
    folder = data / "adventures" / "library" / LEGACY_ID / "visuals"
    folder.mkdir(parents=True)
    image = folder / "портрет.png"
    Image.new("RGB", (32, 48), color="blue").save(image)
    url = f"/data/adventures/library/{LEGACY_ID}/visuals/портрет.png"
    async with TestSessionLocal() as db:
        owner = await db.scalar(select(User).where(User.username == "test_user"))
        db.add(AdventureTemplate(id=LEGACY_ID, title="Одинокий путник", owner_id=owner.id))
        db.add(WorldScene(id="ЛЕС", template_id=LEGACY_ID, label="Лес", description="Тихий лес"))
        await db.commit()
    return image, url


@pytest.mark.parametrize("target_type,target_id", [("cover", LEGACY_ID), ("scene", "ЛЕС")])
async def test_upload_visual_keeps_legacy_ids(auth_client, legacy_world, target_type, target_id):
    image, _ = legacy_world
    response = await auth_client.post(
        f"/api/adventures/{LEGACY_ID}/visuals/upload",
        data={"target_type": target_type, "target_id": target_id},
        files={"file": ("рисунок.png", image.read_bytes(), "image/png")},
    )
    assert response.status_code == 200, response.text
    path = Path(data_url_to_local_path(response.json()["image_url"]))
    assert path.is_file() and LEGACY_ID in path.parts


async def test_reused_unicode_image_remains_inside_target_adventure(legacy_world):
    image, url = legacy_world
    copied = copy_source_asset_to_current_adventure(url, template_id="target", entity_type="npc")
    assert copied is not None
    path = Path(data_url_to_local_path(copied))
    assert path.read_bytes() == image.read_bytes()
    assert "target" in path.parts and path != image


async def test_upload_rejects_unsafe_unicode_target(auth_client, legacy_world):
    image, _ = legacy_world
    response = await auth_client.post(
        f"/api/adventures/{LEGACY_ID}/visuals/upload",
        data={"target_type": "scene", "target_id": "ЛЕС/../other"},
        files={"file": ("рисунок.png", image.read_bytes(), "image/png")},
    )
    assert response.status_code == 400
