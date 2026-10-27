"""The exported manifest keeps the start scene, so an imported copy starts where the original does."""

import pytest
from sqlalchemy import select

from backend.engine.adventure_exporter import AdventureExporter
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.models.world_entity import WorldExit, WorldScene
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio

TEMPLATE_ID = "start-scene-export"


async def _seed(db, original_manifest: dict | None) -> None:
    user = (await db.execute(select(User).limit(1))).scalars().first()
    db.add_all(
        [
            AdventureTemplate(
                id=TEMPLATE_ID,
                title="Diner",
                owner_id=user.id,
                original_manifest=original_manifest,
            ),
            # Alphabetically first, but not the start scene.
            WorldScene(
                id="BACK_KITCHEN", template_id=TEMPLATE_ID, label="Kitchen", description="Hot."
            ),
            WorldScene(
                id="DINER_COUNTER", template_id=TEMPLATE_ID, label="Counter", description="Chrome."
            ),
            WorldExit(
                template_id=TEMPLATE_ID,
                session_id=None,
                from_scene_id="DINER_COUNTER",
                to_scene_id="BACK_KITCHEN",
                label="Swinging door",
                is_locked=False,
            ),
        ]
    )
    await db.commit()


async def _export_start(original_manifest: dict | None) -> tuple[dict, list[str]]:
    async with TestSessionLocal() as db:
        await _seed(db, original_manifest)
        manifest = await AdventureExporter.build_full_manifest(db, TEMPLATE_ID)
    return manifest, [scene["id"] for scene in manifest["scenes"]]


async def test_export_keeps_explicit_start_scene(auth_client, setup_test_db):
    # Arrange
    original = {"start_scene_id": "DINER_COUNTER", "scenes": [{"id": "BACK_KITCHEN"}]}

    # Act
    manifest, scene_ids = await _export_start(original)

    # Assert
    assert manifest["start_scene_id"] == "DINER_COUNTER"
    assert manifest["adventure"]["start_scene_id"] == "DINER_COUNTER"
    assert scene_ids == ["DINER_COUNTER", "BACK_KITCHEN"]


async def test_export_resolves_entry_scene_without_manifest(auth_client, setup_test_db):
    # Act
    manifest, scene_ids = await _export_start(None)

    # Assert: the counter has no incoming exit, so sessions start there.
    assert manifest["start_scene_id"] == "DINER_COUNTER"
    assert scene_ids[0] == "DINER_COUNTER"
