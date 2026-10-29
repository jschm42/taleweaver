import io
import json
import os
import zipfile
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from backend.engine.adventures.adventure_exporter import AdventureExporter
from backend.engine.adventures.adventure_importer import AdventureTemplateImporter
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.user import User
from backend.models.world_entity import WorldScene

_ADVENTURE_ID = "portability-test-999"
_ASSET_FILES = ["cover.jpg", "hero.jpg", "start.jpg"]
_INIT_SCRIPT = "def panel_choice(index):\n    tw.vars.set('panel_result', index)\n"
_WORLD_SCRIPTS = [
    {
        "id": "SCRIPT_GREETING",
        "name": "Greeting",
        "trigger": "on_enter_scene",
        "target_id": "SCENE_START",
        "code": "tw.story.system_message('Hello')",
    }
]


async def _ensure_user(db) -> User:
    user_res = await db.execute(select(User).where(User.username == "testuser"))
    user = user_res.scalars().first()
    if not user:
        user = User(username="testuser", hashed_password="fake", role="user")
        db.add(user)
        await db.flush()
    return user


async def _seed_full_adventure(db, owner_id: str) -> None:
    """Adventure, protagonist and scene with every portable field populated."""
    library = f"/data/adventures/library/{_ADVENTURE_ID}"
    db.add(
        AdventureTemplate(
            id=_ADVENTURE_ID,
            owner_id=owner_id,
            title="Master Portability Test",
            teaser="Verifying every single field.",
            version="1.0.0",
            language="English",
            plot="The plot must survive.",
            rules="The rules must be preserved.",
            intro_text="Welcome to the test.",
            completed_condition="Victory.",
            gameover_condition="Defeat.",
            starting_timestamp=480,
            time_system="chronology",
            time_config={"custom": "data"},
            game_over_rules={"hardcore": True},
            allow_dynamic_items=False,
            image_url=f"{library}/cover.jpg",
            is_ready=True,
            creation_status="Ready",
            original_manifest={"scripts": _WORLD_SCRIPTS, "init_script": _INIT_SCRIPT},
        )
    )
    await db.flush()
    db.add(
        Avatar(
            template_id=_ADVENTURE_ID,
            user_id=owner_id,
            name="Test Hero",
            role="Survivor",
            description="A hero with many stats.",
            goal="Survive the test.",
            character="Brave.",
            profile_image=f"{library}/hero.jpg",
            hp=150,
            max_hp=150,
            exp=500,
            strength=15,
            dexterity=12,
            intelligence=10,
            wisdom=8,
            charisma=14,
            armor_class=15,
            status_effects=["Test Buff"],
            stats={"luck": 5},
            inventory=[],
            equipment={},
        )
    )
    db.add(
        WorldScene(
            id="SCENE_START",
            template_id=_ADVENTURE_ID,
            label="Start",
            description="The beginning.",
            image_url=f"{library}/scenes/start.jpg",
        )
    )
    await db.commit()


def _patch_export_filesystem(monkeypatch) -> None:
    """Every data path exists and ZIP writes store fake bytes instead of real files."""

    def fake_zip_write(self, filename, arcname=None, compress_type=None):
        self.writestr(arcname or filename, b"fake_binary_data")

    monkeypatch.setattr("os.path.exists", lambda p: True)
    monkeypatch.setattr("zipfile.ZipFile.write", fake_zip_write)
    monkeypatch.setattr("os.walk", lambda t, **k: [(t, [], list(_ASSET_FILES))])
    monkeypatch.setattr("os.makedirs", lambda *a, **k: None)


def _patch_import_filesystem(monkeypatch) -> None:
    """Assets read back as fake bytes; extracted files are written nowhere."""
    import builtins

    original_zip_read = zipfile.ZipFile.read
    original_open = builtins.open
    original_isfile = os.path.isfile

    def fake_zip_read(self, name):
        return original_zip_read(self, name) if name == "adventure.adv" else b"restored_asset_data"

    class MockFile:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return None

        def write(self, d):
            return None

        def read(self, *a):
            return b"fake"

    def fake_open(*args, **kwargs):
        # Only asset extraction ('wb') is mocked.
        if len(args) > 1 and "wb" in args[1]:
            return MockFile()
        return original_open(*args, **kwargs)

    def fake_isfile(path):
        markers = (_ADVENTURE_ID, "library", *_ASSET_FILES)
        return any(marker in path for marker in markers) or original_isfile(path)

    monkeypatch.setattr("zipfile.ZipFile.read", fake_zip_read)
    monkeypatch.setattr("builtins.open", fake_open)
    monkeypatch.setattr("os.path.isfile", fake_isfile)
    # Avoid actual thumbnail generation.
    monkeypatch.setattr(
        "backend.engine.media.media_engine.MediaEngine.ensure_thumbnails", AsyncMock()
    )
    monkeypatch.setattr(
        "backend.engine.media.media_engine.MediaEngine.generate_placeholder",
        AsyncMock(return_value="/data/placeholder.jpg"),
    )


def _assert_manifest(adz_bytes: bytes) -> None:
    with zipfile.ZipFile(io.BytesIO(adz_bytes)) as z:
        assert "adventure.adv" in z.namelist()
        manifest = json.loads(z.read("adventure.adv"))
    assert manifest["adventure"]["time_system"] == "chronology"
    assert manifest["adventure"]["allow_dynamic_items"] is False
    assert manifest["protagonist"]["goal"] == "Survive the test."
    assert manifest["protagonist"]["profile_image"] == "assets/hero.jpg"


async def _delete_seeded_adventure(db) -> None:
    from sqlalchemy import delete

    await db.execute(delete(WorldScene).where(WorldScene.template_id == _ADVENTURE_ID))
    await db.execute(delete(Avatar).where(Avatar.template_id == _ADVENTURE_ID))
    await db.execute(delete(AdventureTemplate).where(AdventureTemplate.id == _ADVENTURE_ID))
    await db.commit()


async def _assert_restored(db) -> None:
    res = await db.execute(
        select(AdventureTemplate).where(AdventureTemplate.title == "Master Portability Test")
    )
    restored_adv = res.scalars().first()
    assert restored_adv is not None
    assert restored_adv.time_system == "chronology"
    assert restored_adv.allow_dynamic_items is False
    assert restored_adv.plot == "The plot must survive."
    # tw.dialog handlers and world scripts live in the manifest and must survive the round trip.
    assert restored_adv.init_script == _INIT_SCRIPT
    assert restored_adv.original_manifest["scripts"][0]["id"] == "SCRIPT_GREETING"

    av_res = await db.execute(select(Avatar).where(Avatar.template_id == restored_adv.id))
    restored_avatar = av_res.scalars().first()
    assert restored_avatar is not None
    assert restored_avatar.goal == "Survive the test."
    assert restored_avatar.strength == 15
    assert restored_avatar.status_effects == ["Test Buff"]
    # Image should be re-mapped to the new library path
    assert restored_avatar.profile_image.startswith("/data/adventures/library/")
    assert "hero.jpg" in restored_avatar.profile_image


@pytest.mark.asyncio
async def test_full_portability_cycle(setup_test_db, monkeypatch):
    """
    Verifies that an adventure can be exported to ADZ and imported back
    with 100% field parity and correct asset re-mapping.
    """
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user = await _ensure_user(db)
        await _seed_full_adventure(db, user.id)

        _patch_export_filesystem(monkeypatch)
        adz_bytes = await AdventureExporter.export_adz(db, _ADVENTURE_ID)
        assert len(adz_bytes) > 0
        _assert_manifest(adz_bytes)

        # Delete the original adventure to simulate a clean import.
        await _delete_seeded_adventure(db)
        _patch_import_filesystem(monkeypatch)
        success = await AdventureTemplateImporter.import_adz(db, adz_bytes, owner_id=user.id)
        assert success is True
        await _assert_restored(db)
