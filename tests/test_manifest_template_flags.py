"""Template flags (adventure creator, damage rules) survive manifest application on import."""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from backend.engine.adventures.adventure_exporter import AdventureExporter
from backend.engine.world.world_manifest_applier import apply_manifest
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.models.world_entity import WorldScene
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio

SOURCE_ID = "flags-source"
TARGET_ID = "flags-target"


@pytest.fixture(autouse=True)
def _no_placeholder(monkeypatch):
    monkeypatch.setattr(
        "backend.engine.media.media_engine.MediaEngine.generate_placeholder",
        AsyncMock(return_value="/data/placeholder.svg"),
    )


def _template(template_id: str, owner_id: int, *, creator_flag: bool) -> AdventureTemplate:
    return AdventureTemplate(
        id=template_id,
        title="Flags",
        owner_id=owner_id,
        rule_enforcement_mode="rpg",
        language="de",
        is_adventure_generator=creator_flag,
        can_damage_npcs=False,
        npcs_can_damage_protagonist=False,
    )


async def _load(db, template_id: str) -> AdventureTemplate:
    stmt = select(AdventureTemplate).where(AdventureTemplate.id == template_id)
    return (await db.execute(stmt)).scalars().one()


async def test_reduced_world_manifest_keeps_stored_flags(auth_client, setup_test_db):
    # Arrange: the .adz importer passes a world manifest without the template flags.
    async with TestSessionLocal() as db:
        user = (await db.execute(select(User).limit(1))).scalars().first()
        db.add(_template(TARGET_ID, user.id, creator_flag=True))
        await db.commit()
        world_manifest = {
            "protagonist": {"name": "Hero"},
            "scenes": [{"id": "START", "label": "Start", "description": "A room."}],
        }

        # Act
        await apply_manifest(db, TARGET_ID, world_manifest)

    # Assert
    async with TestSessionLocal() as db:
        adventure = await _load(db, TARGET_ID)
        assert adventure.is_adventure_generator is True
        assert adventure.can_damage_npcs is False
        assert adventure.npcs_can_damage_protagonist is False
        assert adventure.language == "de"


async def test_exported_creator_flag_is_applied_to_target(auth_client, setup_test_db):
    # Arrange
    async with TestSessionLocal() as db:
        user = (await db.execute(select(User).limit(1))).scalars().first()
        db.add_all(
            [
                _template(SOURCE_ID, user.id, creator_flag=True),
                _template(TARGET_ID, user.id, creator_flag=False),
                WorldScene(id="HALL", template_id=SOURCE_ID, label="Hall", description="Wide."),
            ]
        )
        await db.commit()
        manifest = await AdventureExporter.build_full_manifest(db, SOURCE_ID)

        # Act
        await apply_manifest(db, TARGET_ID, manifest)

    # Assert
    async with TestSessionLocal() as db:
        adventure = await _load(db, TARGET_ID)
        assert manifest["adventure"]["is_adventure_generator"] is True
        assert adventure.is_adventure_generator is True
