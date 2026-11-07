"""Scene background music (``music_url``) through blueprint, generation, editor and export."""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from backend.api.routes.adventures.editing.entity_update.scene_exit import update_scene
from backend.api.routes.adventures.editing.schemas import EntityUpdateRequest
from backend.engine.adventures.adventure_exporter import AdventureExporter
from backend.engine.adventures.adventure_import_support import localize_scene_music
from backend.engine.blueprint import analyze_blueprint, apply_blueprint
from backend.engine.world.scene_fields import scene_content, scene_content_from_dict
from backend.engine.world.world_manifest_applier import apply_manifest
from backend.engine.world.world_schemas import WorldSceneSchema
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.models.world_entity import WorldScene
from tests.conftest import TestSessionLocal

MUSIC = "/data/adventures/library/music-src/assets/cave_theme.ogg"


@pytest.mark.parametrize("key", ["music", "music_url"])
def test_scene_music_key_reaches_the_generated_scene(key):
    # Arrange
    text = f"[Scene: CAVE] The Cave\n{key}: {MUSIC}\n"
    blueprint, _missing = analyze_blueprint(text)
    manifest = {"scenes": [{"id": "CAVE", "name": "Cave", "description": "Damp."}]}

    # Act
    violations = apply_blueprint(manifest, blueprint)

    # Assert
    assert blueprint.errors == []
    assert violations == []
    assert manifest["scenes"][0]["music_url"] == MUSIC
    assert WorldSceneSchema.model_validate(manifest["scenes"][0]).music_url == MUSIC


def test_scene_content_copies_music_url():
    # Arrange
    scene = WorldScene(id="CAVE", label="Cave", description="Damp.", music_url=MUSIC)

    # Act
    from_row = scene_content(scene)
    from_dict = scene_content_from_dict({"id": "CAVE", "music_url": MUSIC})

    # Assert
    assert from_row["music_url"] == MUSIC
    assert from_dict["music_url"] == MUSIC


def test_import_maps_bundled_music_to_extracted_asset():
    # Arrange
    scenes = [{"id": "CAVE", "music_url": "assets/cave_theme.ogg"}, {"id": "HALL"}]
    mapping = {"assets/cave_theme.ogg": MUSIC}

    # Act
    localize_scene_music(scenes, mapping)

    # Assert
    assert scenes[0]["music_url"] == MUSIC
    assert "music_url" not in scenes[1]


@pytest.mark.asyncio
async def test_editor_update_sets_clears_and_syncs_music(auth_client, setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange
        user = (await db.execute(select(User).limit(1))).scalars().first()
        adv = AdventureTemplate(
            id="music-edit",
            title="Music Edit",
            owner_id=user.id,
            original_manifest={"scenes": [{"id": "CAVE", "name": "Cave"}]},
        )
        db.add_all(
            [adv, WorldScene(id="CAVE", template_id="music-edit", label="Cave", description="D")]
        )
        await db.flush()
        set_music = EntityUpdateRequest(
            target_type="scene", target_id="CAVE", music_url=f"  {MUSIC} "
        )
        clear_music = EntityUpdateRequest(target_type="scene", target_id="CAVE", music_url="")

        # Act
        await update_scene(db, "music-edit", adv, set_music)
        scene = (await db.execute(select(WorldScene).where(WorldScene.id == "CAVE"))).scalar_one()
        stored, synced = scene.music_url, adv.original_manifest["scenes"][0]["music_url"]
        await update_scene(db, "music-edit", adv, clear_music)

        # Assert
        assert stored == MUSIC
        assert synced == MUSIC
        assert scene.music_url is None
        assert adv.original_manifest["scenes"][0]["music_url"] is None


@pytest.mark.asyncio
async def test_scene_music_survives_export_and_apply(auth_client, setup_test_db, monkeypatch):
    monkeypatch.setattr(
        "backend.engine.media.media_engine.MediaEngine.generate_placeholder",
        AsyncMock(return_value="/data/placeholder.svg"),
    )
    async with TestSessionLocal() as db:
        # Arrange
        user = (await db.execute(select(User).limit(1))).scalars().first()
        db.add_all(
            [
                AdventureTemplate(id="music-src", title="Music", owner_id=user.id),
                AdventureTemplate(id="music-dst", title="Music Copy", owner_id=user.id),
                WorldScene(
                    id="CAVE",
                    template_id="music-src",
                    label="Cave",
                    description="Damp.",
                    music_url=MUSIC,
                ),
            ]
        )
        await db.commit()
        manifest = await AdventureExporter.build_full_manifest(db, "music-src")

        # Act
        await apply_manifest(db, "music-dst", manifest)

    # Assert
    async with TestSessionLocal() as db:
        scene = (
            (await db.execute(select(WorldScene).where(WorldScene.template_id == "music-dst")))
            .scalars()
            .first()
        )
        assert manifest["scenes"][0]["music_url"] == MUSIC
        assert scene.music_url == MUSIC
