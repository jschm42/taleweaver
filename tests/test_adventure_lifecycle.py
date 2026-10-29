import io
import json
import os
import zipfile
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.engine.adventures.adventure_exporter import AdventureExporter
from backend.engine.adventures.adventure_importer import AdventureTemplateImporter
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldScene

pytestmark = pytest.mark.asyncio


async def _seed_adventure(db: AsyncSession, user_id: str) -> str:
    """Seeds a full adventure with all entity types."""
    adv = AdventureTemplate(
        id="test-adv-123",
        owner_id=user_id,
        title="Lifecycle Test",
        teaser="A test for export and import.",
        original_prompt="Full context here.",
        plot="Test plot",
        rules="Test rules",
        intro_text="Welcome to the lifecycle test adventure.",
        completed_condition="Win",
        gameover_condition="Lose",
        starting_timestamp=480,
        image_url="/data/adventures/test-adv-123/cover.jpg",
        creator="Test Creator",
        copyright="Test Copyright",
        license="MIT",
    )
    db.add(adv)
    await db.flush()

    avatar = Avatar(
        template_id=adv.id,
        user_id=user_id,
        name="Test Hero",
        role="Tester",
        description="A hero for testing.",
        profile_image="/data/adventures/test-adv-123/hero.jpg",
        stats={"str": 15},
        inventory=[{"id": "POTION_1", "name": "Test Potion"}],
        equipment={"MainHand": {"id": "SWORD_1", "name": "Test Sword"}},
    )
    db.add(avatar)

    scene = WorldScene(
        id="SCENE_1",
        template_id=adv.id,
        label="Test Scene",
        description="A scene for testing.",
        image_url="/data/adventures/test-adv-123/scenes/scene1.jpg",
    )
    db.add(scene)

    npc = WorldEntity(
        id="NPC_1",
        template_id=adv.id,
        entity_type="NPC",
        name="Test NPC",
        description="An NPC for testing.",
        current_scene_id="SCENE_1",
        image_url="/data/adventures/test-adv-123/entities/npc1.jpg",
    )
    db.add(npc)

    obj = WorldEntity(
        id="SWORD_1",
        template_id=adv.id,
        entity_type="OBJECT",
        name="Test Sword",
        description="A sword for testing.",
        current_scene_id="INVENTORY",
        item_type="WEAPON",
    )
    db.add(obj)

    obj2 = WorldEntity(
        id="POTION_1",
        template_id=adv.id,
        entity_type="OBJECT",
        name="Test Potion",
        description="A potion for testing.",
        current_scene_id="INVENTORY",
        item_type="CONSUMABLE",
    )
    db.add(obj2)

    await db.commit()
    return adv.id


async def test_export_adv_objects_omit_null_and_npc_fields(auth_client, setup_test_db):
    """Object export should omit null/NPC-only fields while preserving meaningful zero values."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user_res = await db.execute(select(User).limit(1))
        user = user_res.scalars().first()
        adventure_id = await _seed_adventure(db, user.id)

        object_res = await db.execute(
            select(WorldEntity).where(
                WorldEntity.template_id == adventure_id,
                WorldEntity.id == "SWORD_1",
            )
        )
        obj = object_res.scalars().first()
        assert obj is not None

        obj.stat_modifier_strength = 0
        obj.metadata_json = {
            "hp_change": 0,
            "stat_modifier_strength": 0,
            "mana_change": None,
        }
        await db.commit()

        manifest = await AdventureExporter.build_full_manifest(db, adventure_id)
        exported_obj = next((o for o in manifest["objects"] if o["id"] == "SWORD_1"), None)

        assert exported_obj is not None
        assert exported_obj.get("stat_modifier_strength") == 0
        assert exported_obj.get("hp_change") == 0
        assert "stat_modifier_strength" not in exported_obj.get("metadata_json", {})

        # Null and NPC-only attributes should be excluded from object payloads.
        assert "npc_type" not in exported_obj
        assert "movement_type" not in exported_obj
        assert "goal" not in exported_obj
        assert "character" not in exported_obj
        assert "hp" not in exported_obj
        assert "mana" not in exported_obj
        assert "session_id" not in exported_obj
        assert "pk" not in exported_obj
        assert "created_at" not in exported_obj
        assert "updated_at" not in exported_obj

        assert "mana_change" not in exported_obj.get("metadata_json", {})


_FAKE_ASSET_FILES = ["cover.jpg", "hero.jpg", "scene1.jpg", "npc1.jpg"]


def _patch_export_filesystem(monkeypatch) -> None:
    """Simulates the adventure's image files so export never touches the disk."""
    original_exists = os.path.exists
    original_walk = os.walk

    def fake_exists(path):
        return any(name in path for name in _FAKE_ASSET_FILES) or original_exists(path)

    def fake_walk(top, topdown=True, onerror=None, followlinks=False):
        if "test-adv-123" in top:
            yield (top, [], list(_FAKE_ASSET_FILES))
        else:
            yield from original_walk(top, topdown, onerror, followlinks)

    monkeypatch.setattr("os.path.exists", fake_exists)
    monkeypatch.setattr("zipfile.ZipFile.write", lambda *args, **kwargs: None)
    monkeypatch.setattr("os.walk", fake_walk)
    monkeypatch.setattr("os.makedirs", lambda *args, **kwargs: None)
    # Avoid placeholder generation errors in MediaEngine.
    monkeypatch.setattr(
        "backend.engine.media.media_engine.MediaEngine.generate_svg_placeholder",
        AsyncMock(return_value="/data/fake_placeholder.svg"),
    )
    monkeypatch.setattr(
        "backend.engine.media.media_engine.MediaEngine.generate_entity_image",
        AsyncMock(return_value="/data/fake_portrait.jpg"),
    )


def _patch_import_filesystem(monkeypatch) -> dict:
    """Serves dummy bytes for assets and captures extracted files in memory."""
    import builtins

    original_zip_read = zipfile.ZipFile.read
    original_open = builtins.open
    written: dict = {}

    def fake_zip_read(self, name):
        return original_zip_read(self, name) if name == "adventure.adv" else b"fake_image_data"

    class MockFile:
        def __init__(self, name):
            self.name = name

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def write(self, data):
            written[self.name] = data

    def fake_open(name, mode="r", *args, **kwargs):
        if "wb" in mode:
            return MockFile(name)
        return original_open(name, mode, *args, **kwargs)

    monkeypatch.setattr("zipfile.ZipFile.read", fake_zip_read)
    monkeypatch.setattr("builtins.open", fake_open)
    return written


def _assert_exported_manifest(adz_bytes: bytes) -> None:
    with zipfile.ZipFile(io.BytesIO(adz_bytes)) as z:
        assert "adventure.adv" in z.namelist()
        manifest = json.loads(z.read("adventure.adv"))

    adventure = manifest["adventure"]
    assert adventure["title"] == "Lifecycle Test"
    assert adventure["plot"] == "Test plot"
    assert adventure["rules"] == "Test rules"
    assert adventure["intro_text"] == "Welcome to the lifecycle test adventure."
    assert adventure["completed_condition"] == "Win"
    assert adventure["starting_timestamp"] == 480
    assert adventure["creator"] == "Test Creator"
    assert adventure["copyright"] == "Test Copyright"
    assert adventure["license"] == "MIT"

    protagonist = manifest["protagonist"]
    assert protagonist["name"] == "Test Hero"
    assert protagonist["profile_image"] == "assets/hero.jpg"
    assert protagonist["starting_inventory"] == ["POTION_1"]
    assert protagonist["starting_equipment"]["MainHand"] == "SWORD_1"
    assert len(manifest["scenes"]) == 1
    assert manifest["scenes"][0]["image_url"] == "assets/scene1.jpg"


async def _delete_adventure(db: AsyncSession, adventure_id: str) -> None:
    """Removes the seeded adventure so the import does not hit the duplicate-title check."""
    from sqlalchemy import delete

    await db.execute(delete(WorldEntity).where(WorldEntity.template_id == adventure_id))
    await db.execute(delete(WorldScene).where(WorldScene.template_id == adventure_id))
    await db.execute(delete(Avatar).where(Avatar.template_id == adventure_id))
    await db.execute(delete(AdventureTemplate).where(AdventureTemplate.id == adventure_id))
    await db.commit()


async def test_adventure_adz_export_import_cycle(auth_client, setup_test_db, monkeypatch):
    """Verifies that an adventure can be exported to ADZ and imported back with all data intact."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user_res = await db.execute(select(User).limit(1))
        user = user_res.scalars().first()
        adventure_id = await _seed_adventure(db, user.id)

        # 1. Export
        _patch_export_filesystem(monkeypatch)
        adz_bytes = await AdventureExporter.export_adz(db, adventure_id)
        assert len(adz_bytes) > 0
        _assert_exported_manifest(adz_bytes)

        # 2. Import as a new adventure for the same user
        _patch_import_filesystem(monkeypatch)
        await _delete_adventure(db, adventure_id)
        success = await AdventureTemplateImporter.import_adz(db, adz_bytes, owner_id=user.id)
        assert success is True


async def test_adventure_import_restores_protagonist(auth_client, setup_test_db, monkeypatch):
    """Specifically verifies that the protagonist record is created and linked correctly during import."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user_res = await db.execute(select(User).limit(1))
        user = user_res.scalars().first()

        manifest = {
            "format": "TaleWeaver",
            "version": "1.1",
            "adventure": {
                "title": "Import Protagonist Test",
                "teaser": "Testing character restoration.",
                "context": "Context",
                "plot": "Import plot",
                "rules": "Import rules",
                "intro_text": "Import intro text",
                "completed_condition": "Win if...",
                "gameover_condition": "Lose if...",
            },
            "protagonist": {
                "name": "Imported Hero",
                "role": "Wanderer",
                "description": "Lost but not forgotten.",
                "profile_image": "assets/hero.jpg",
                "hp": 150,
                "stats": {"str": 12},
            },
            "scenes": [{"id": "START", "name": "Start", "description": "Start"}],
        }

        # Create a mock ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as z:
            z.writestr("adventure.adv", json.dumps(manifest))
            z.writestr("assets/hero.jpg", b"fake_data")

        # Mock file operations for extraction
        import builtins

        original_open = builtins.open

        def fake_open(name, mode="r", *args, **kwargs):
            if "wb" in mode:
                return io.BytesIO()
            return original_open(name, mode, *args, **kwargs)

        original_isfile = os.path.isfile

        def fake_isfile(path):
            if "hero.jpg" in path:
                return True
            return original_isfile(path)

        monkeypatch.setattr("os.path.isfile", fake_isfile)
        monkeypatch.setattr("os.makedirs", lambda *args, **kwargs: None)
        monkeypatch.setattr("builtins.open", fake_open)

        # Mock MediaEngine
        monkeypatch.setattr(
            "backend.engine.media.media_engine.MediaEngine.generate_svg_placeholder",
            AsyncMock(return_value="/data/fake_placeholder.svg"),
        )
        monkeypatch.setattr(
            "backend.engine.media.media_engine.MediaEngine.generate_entity_image",
            AsyncMock(return_value="/data/fake_portrait.jpg"),
        )

        success = await AdventureTemplateImporter.import_adz(
            db, zip_buffer.getvalue(), owner_id=user.id
        )
        assert success is True

        # Find the new adventure
        res = await db.execute(
            select(AdventureTemplate).where(AdventureTemplate.title == "Import Protagonist Test")
        )
        new_adv = res.scalars().first()
        assert new_adv is not None
        assert new_adv.plot == "Import plot"
        assert new_adv.rules == "Import rules"
        assert new_adv.intro_text == "Import intro text"
        assert new_adv.completed_condition == "Win if..."

        # Check Avatar
        av_res = await db.execute(select(Avatar).where(Avatar.template_id == new_adv.id))
        avatar = av_res.scalars().first()
        assert avatar is not None
        assert avatar.name == "Imported Hero"
        assert avatar.hp == 150
        assert avatar.stats["str"] == 12
        assert avatar.profile_image.startswith("/data/adventures/")
        assert "hero.jpg" in avatar.profile_image


async def test_build_full_manifest_is_read_only(auth_client, setup_test_db):
    """build_full_manifest must not mutate the database.

    Regression test: previously the exporter called db.add(avatar) and
    db.flush() while building the export, which caused "database is locked"
    errors on SQLite when a background task (e.g. world generation) held a
    write lock. The avatar's inventory/equipment and any newly created
    WorldEntity rows must be left exactly as they were after a manifest build.
    """
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user_res = await db.execute(select(User).limit(1))
        user = user_res.scalars().first()
        adventure_id = await _seed_adventure(db, user.id)

    # Snapshot avatar state before the export
    async with TestSessionLocal() as db:
        av_res = await db.execute(select(Avatar).where(Avatar.template_id == adventure_id))
        avatar_before = av_res.scalars().first()
        inv_before = list(avatar_before.inventory or [])
        equip_before = dict(avatar_before.equipment or {})

        ent_res = await db.execute(
            select(WorldEntity).where(WorldEntity.template_id == adventure_id)
        )
        entities_before = sorted(ent.id for ent in ent_res.scalars().all())

    # Build manifest (this used to mutate the DB)
    async with TestSessionLocal() as db:
        manifest = await AdventureExporter.build_full_manifest(db, adventure_id)

    # Verify avatar/inventory/equipment unchanged in DB
    async with TestSessionLocal() as db:
        av_res = await db.execute(select(Avatar).where(Avatar.template_id == adventure_id))
        avatar_after = av_res.scalars().first()
        assert avatar_after is not None
        assert list(avatar_after.inventory or []) == inv_before
        assert dict(avatar_after.equipment or {}) == equip_before

        ent_res = await db.execute(
            select(WorldEntity).where(WorldEntity.template_id == adventure_id)
        )
        entities_after = sorted(ent.id for ent in ent_res.scalars().all())
        assert entities_after == entities_before

    # Verify manifest itself is still well-formed and uses cleaned ID references
    assert manifest["protagonist"]["starting_inventory"] == ["POTION_1"]
    assert manifest["protagonist"]["starting_equipment"] == {"MainHand": "SWORD_1"}


async def test_decorative_objects_round_trip_through_manifest(
    auth_client, setup_test_db, monkeypatch
):
    """Decorative objects must round-trip through the export manifest as a structured array.

    Regression test: previously `decorative_objects` were stored by appending a
    "\n\nDECORATIVE_OBJECTS:" suffix to the scene description string. The new
    design uses a dedicated structured column on WorldScene, so the exporter
    must emit it as its own JSON array on each scene.
    """
    from tests.conftest import TestSessionLocal

    expected_decor = ["metal table", "hanging light fixture", "cracked stone floor"]

    async with TestSessionLocal() as db:
        user_res = await db.execute(select(User).limit(1))
        user = user_res.scalars().first()
        adventure_id = await _seed_adventure(db, user.id)

    async with TestSessionLocal() as db:
        scene_res = await db.execute(
            select(WorldScene).where(WorldScene.template_id == adventure_id)
        )
        scene = scene_res.scalars().first()
        assert scene is not None
        scene.decorative_objects = list(expected_decor)
        await db.commit()

    # Build manifest — must include decorative_objects as a structured array,
    # NOT as a suffix in the description string.
    async with TestSessionLocal() as db:
        manifest = await AdventureExporter.build_full_manifest(db, adventure_id)

    scene_in_manifest = next((s for s in manifest["scenes"] if s["id"] == "SCENE_1"), None)
    assert scene_in_manifest is not None
    assert scene_in_manifest.get("decorative_objects") == expected_decor
    assert "DECORATIVE_OBJECTS:" not in (scene_in_manifest.get("description") or "")


async def test_decorative_objects_built_from_structured_field_only(
    monkeypatch, auth_client, setup_test_db
):
    """Memory manager must read decorative_objects from the structured field, not the description."""
    from backend.engine.sessions.memory_manager import MemoryManager
    from backend.models.world_entity import WorldEntity
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user_res = await db.execute(select(User).limit(1))
        user = user_res.scalars().first()
        adventure_id = await _seed_adventure(db, user.id)

    expected_decor = ["glowing orb", "dusty bookshelf"]

    async with TestSessionLocal() as db:
        scene_res = await db.execute(
            select(WorldScene).where(WorldScene.template_id == adventure_id)
        )
        scene = scene_res.scalars().first()
        # Intentionally set ONLY the structured field — description must stay clean.
        scene.decorative_objects = list(expected_decor)
        scene.description = "A quiet study with faded wallpaper."
        await db.commit()

    async with TestSessionLocal() as db:
        scene = (
            (await db.execute(select(WorldScene).where(WorldScene.template_id == adventure_id)))
            .scalars()
            .first()
        )
        entities = (
            (await db.execute(select(WorldEntity).where(WorldEntity.template_id == adventure_id)))
            .scalars()
            .all()
        )

        ctx = MemoryManager._build_location_context(scene, entities, [], "full")
        assert "glowing orb" in ctx
        assert "dusty bookshelf" in ctx
        assert "DECORATIVE_OBJECTS:" not in ctx
        # And the description must be passed through cleanly, no suffix appended.
        assert "A quiet study with faded wallpaper." in ctx


async def test_import_adv_manifest_preserves_nested_adventure_metadata(auth_client, setup_test_db):
    """Importing a freshly-exported ADV must keep `teaser`, `rules`, `language`, etc.

    Regression test: previously `apply_manifest` overwrote these fields with
    `manifest_dict.get("teaser", "")` etc. — but in a standard ADV manifest
    the narrative metadata lives under the `adventure` key, not at the top
    level. The result was a silent wipe of the values to empty strings.
    """
    from backend.engine.adventures.adventure_importer import AdventureTemplateImporter
    from tests.conftest import TestSessionLocal

    payload = {
        "format": "TaleWeaver",
        "version": "1.2",
        "adventure": {
            "title": "Round Trip Metadata",
            "teaser": "A teaser that must survive import.",
            "rules": "Rules that must survive import.",
            "language": "English",
            "plot": "Plot that must survive import.",
            "intro_text": "Intro that must survive import.",
            "walkthrough": "Walkthrough that must survive import.",
            "completed_condition": "Win",
            "gameover_condition": "Lose",
            "rule_enforcement_mode": "rpg",
            "time_per_turn": 10,
            "pacing_minutes": 5,
            "clock_enabled": False,
            "is_adventure_generator": False,
            "starting_timestamp": 0,
            "time_system": "calendar",
            "min_scenes": 1,
            "max_scenes": 3,
            "min_items": 0,
            "max_items": 2,
            "min_containers": 0,
            "max_containers": 1,
            "min_text_logs": 0,
            "max_text_logs": 1,
            "min_quests": 0,
            "max_quests": 1,
            "min_awards": 0,
            "max_awards": 1,
            "version": "1.0",
            "allow_dynamic_items": True,
            "can_damage_npcs": True,
            "npcs_can_damage_protagonist": True,
            "creator": "Round Trip Creator",
            "copyright": "Round Trip Copyright",
            "license": "CC-BY-4.0",
        },
        "protagonist": {
            "name": "Hero",
            "role": "Adventurer",
            "description": "Brave",
            "hp": 100,
            "stamina": 100,
            "mana": 50,
            "starting_inventory": [],
            "starting_equipment": {},
            "stats": {},
            "status_effects": [],
        },
        "scenes": [
            {"id": "START", "label": "Start", "description": "Begin", "decorative_objects": []}
        ],
        "exits": [],
        "npcs": [],
        "objects": [],
        "quests": [],
        "awards": [],
    }

    async with TestSessionLocal() as db:
        user_res = await db.execute(select(User).limit(1))
        user = user_res.scalars().first()
        success = await AdventureTemplateImporter.import_adv_manifest(
            db, payload, owner_id=user.id, allow_session=False
        )
        assert success, "import_adv_manifest returned False"

        adv_res = await db.execute(
            select(AdventureTemplate).where(AdventureTemplate.title == "Round Trip Metadata")
        )
        adv = adv_res.scalars().first()
        assert adv is not None
        assert adv.teaser == "A teaser that must survive import."
        assert adv.rules == "Rules that must survive import."
        assert adv.plot == "Plot that must survive import."
        assert adv.intro_text == "Intro that must survive import."
        # The legacy adventure-wide walkthrough is converted into the first sequence.
        assert adv.sequences[0]["walkthrough"] == "Walkthrough that must survive import."
        assert adv.completed_condition == "Win"
        assert adv.gameover_condition == "Lose"
        assert adv.language == "English"
        assert adv.creator == "Round Trip Creator"
        assert adv.copyright == "Round Trip Copyright"
        assert adv.license == "CC-BY-4.0"


async def test_switch_object_export_import_roundtrip(auth_client, setup_test_db):
    """Verifies that a SWITCH object round-trips correctly through export and import."""
    from sqlalchemy import delete

    from backend.engine.adventures.adventure_importer import AdventureTemplateImporter
    from tests.conftest import TestSessionLocal

    # 1. Seed adventure with a SWITCH object
    async with TestSessionLocal() as db:
        user_res = await db.execute(select(User).limit(1))
        user = user_res.scalars().first()
        adventure_id = await _seed_adventure(db, user.id)

        # Create the SWITCH entity
        switch_obj = WorldEntity(
            id="CHAMBER_CONTROL_SWITCH",
            template_id=adventure_id,
            entity_type="OBJECT",
            name="Chamber Control Switch",
            description="A protected lever assembly.",
            current_scene_id="SCENE_1",
            item_type="SWITCH",
            is_portable=False,
            metadata_json={
                "switch": {
                    "states": ["LOCKED", "ARMED", "ACTIVE"],
                    "initial_state": "LOCKED",
                    "transitions": [
                        {
                            "from": "LOCKED",
                            "to": "ARMED",
                            "gates": {"rule": "Has core"},
                            "fail_message": "Chamber rejects.",
                        }
                    ],
                    "outcomes": [
                        {
                            "on_state": "ARMED",
                            "effects": [{"type": "unlock_exit", "target_id": "EXIT_1"}],
                        }
                    ],
                }
            },
        )
        db.add(switch_obj)
        await db.commit()

    # 2. Export manifest
    async with TestSessionLocal() as db:
        manifest = await AdventureExporter.build_full_manifest(db, adventure_id)

    exported_switch = next(
        (o for o in manifest["objects"] if o["id"] == "CHAMBER_CONTROL_SWITCH"), None
    )
    assert exported_switch is not None
    assert exported_switch.get("item_type") == "SWITCH"
    assert exported_switch.get("switch_states") == ["LOCKED", "ARMED", "ACTIVE"]
    assert exported_switch.get("switch_initial_state") == "LOCKED"
    assert len(exported_switch.get("switch_transitions")) == 1
    assert exported_switch.get("switch_transitions")[0]["from"] == "LOCKED"
    assert len(exported_switch.get("switch_outcomes")) == 1
    assert exported_switch.get("switch_outcomes")[0]["on_state"] == "ARMED"

    # 3. Import
    async with TestSessionLocal() as db:
        # Clean up database records for this template to avoid duplication conflict on import
        await db.execute(delete(WorldEntity).where(WorldEntity.template_id == adventure_id))
        await db.execute(delete(WorldScene).where(WorldScene.template_id == adventure_id))
        await db.execute(delete(Avatar).where(Avatar.template_id == adventure_id))
        await db.execute(delete(AdventureTemplate).where(AdventureTemplate.id == adventure_id))
        await db.commit()

    async with TestSessionLocal() as db:
        success = await AdventureTemplateImporter.import_adv_manifest(
            db, manifest, owner_id=user.id, allow_session=False
        )
        assert success is True

    # 4. Verify in database
    async with TestSessionLocal() as db:
        template_res = await db.execute(
            select(AdventureTemplate).where(
                AdventureTemplate.title == manifest["adventure"]["title"]
            )
        )
        new_template = template_res.scalars().first()
        assert new_template is not None
        new_template_id = new_template.id

        res = await db.execute(
            select(WorldEntity).where(
                WorldEntity.template_id == new_template_id,
                WorldEntity.id == "CHAMBER_CONTROL_SWITCH",
            )
        )
        imported_switch = res.scalars().first()
        assert imported_switch is not None
        assert imported_switch.item_type == "SWITCH"
        assert imported_switch.is_portable is False

        switch_config = imported_switch.metadata_json.get("switch")
        assert switch_config is not None
        assert switch_config.get("states") == ["LOCKED", "ARMED", "ACTIVE"]
        assert switch_config.get("initial_state") == "LOCKED"
        assert len(switch_config.get("transitions")) == 1
        assert len(switch_config.get("outcomes")) == 1


async def test_init_script_survives_adv_export_import(auth_client, setup_test_db):
    """The global init_script (e.g. tw.dialog handlers) must be part of the .adv export."""
    from tests.conftest import TestSessionLocal

    init_script = "def on_bomb_wire(answ):\n    tw.vars.set('answer', answ)\n"
    async with TestSessionLocal() as db:
        user = (await db.execute(select(User).limit(1))).scalars().first()
        adventure_id = await _seed_adventure(db, user.id)
        adv = await db.get(AdventureTemplate, adventure_id)
        adv.init_script = init_script
        await db.commit()

    async with TestSessionLocal() as db:
        manifest = await AdventureExporter.build_full_manifest(db, adventure_id)
    assert manifest["init_script"] == init_script.strip()

    async with TestSessionLocal() as db:
        await _delete_adventure(db, adventure_id)
        assert await AdventureTemplateImporter.import_adv_manifest(db, manifest, owner_id=user.id)
        imported = (await db.execute(select(AdventureTemplate))).scalars().first()
        assert imported.init_script == init_script.strip()


async def test_editor_response_includes_init_script(auth_client, setup_test_db):
    """The editor loads init_script through AdventureTemplateResponse to make it editable."""
    from backend.api.routes.adventures.schemas import AdventureTemplateResponse
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user = (await db.execute(select(User).limit(1))).scalars().first()
        adventure_id = await _seed_adventure(db, user.id)
        adv = await db.get(AdventureTemplate, adventure_id)
        adv.init_script = "def helper():\n    return 1"
        await db.commit()
        await db.refresh(adv)

        response = AdventureTemplateResponse.model_validate(adv).model_dump()

    assert response["init_script"] == "def helper():\n    return 1"
