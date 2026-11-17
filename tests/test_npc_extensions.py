"""Extension namespaces in NPC ``metadata_json`` survive editing, export and import."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from backend.core.npc_extensions import (
    MAX_NPC_EXTENSIONS_BYTES,
    normalize_npc_metadata_extensions,
    split_npc_extensions,
)
from backend.engine.adventures.adventure_exporter import AdventureExporter
from backend.engine.adventures.adventure_importer import AdventureTemplateImporter
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.models.world_entity import WorldEntity
from tests.conftest import TestSessionLocal
from tests.test_adventure_lifecycle import _delete_adventure, _seed_adventure

AGENT_RUNTIME = {
    "schema_version": 1,
    "autonomy": "reactive",
    "initial_state": {"situation": "Guards the gate.", "relationships": []},
    "future_field": None,
    "x_unknown": {"nested": None},
}


def test_split_separates_engine_settings_from_extensions():
    # Arrange
    metadata = {
        "attack_mode": "PASSIVE",
        "companion": {"recruitable": True},
        "agent_runtime": AGENT_RUNTIME,
    }

    # Act
    settings, extensions = split_npc_extensions(metadata)

    # Assert
    assert settings == {"attack_mode": "PASSIVE", "companion": {"recruitable": True}}
    assert extensions == {"agent_runtime": AGENT_RUNTIME}


def test_normalize_drops_invalid_and_oversized_namespaces():
    # Arrange
    metadata = {
        "attack_mode": "PASSIVE",
        "Bad Key": {"schema_version": 1},
        "big": {"schema_version": 1, "blob": "x" * MAX_NPC_EXTENSIONS_BYTES},
        "agent_runtime": AGENT_RUNTIME,
    }

    # Act
    result = normalize_npc_metadata_extensions(metadata)

    # Assert
    assert result == {"attack_mode": "PASSIVE", "agent_runtime": AGENT_RUNTIME}


def test_normalize_handles_missing_metadata():
    # Arrange / Act / Assert
    assert normalize_npc_metadata_extensions(None) == {}


async def _npc_row(db, template_id: str) -> WorldEntity:
    query = select(WorldEntity).where(
        WorldEntity.template_id == template_id, WorldEntity.entity_type == "NPC"
    )
    return (await db.execute(query)).scalars().first()


async def _seed_npc_extension(db, user_id: str) -> str:
    adventure_id = await _seed_adventure(db, user_id)
    npc = await _npc_row(db, adventure_id)
    npc.metadata_json = {**(npc.metadata_json or {}), "agent_runtime": AGENT_RUNTIME}
    flag_modified(npc, "metadata_json")
    await db.commit()
    return adventure_id


def _exported_npc(manifest: dict) -> dict:
    return next(n for n in manifest["npcs"] if n["id"] == "NPC_1")


@pytest.mark.asyncio
async def test_npc_extension_survives_edit_export_and_import(auth_client, setup_test_db):
    # Arrange
    async with TestSessionLocal() as db:
        user = (await db.execute(select(User).limit(1))).scalars().first()
        adventure_id = await _seed_npc_extension(db, user.id)

    # Act
    resp = await auth_client.patch(
        f"/api/adventures/{adventure_id}/editor/entity",
        json={"target_type": "npc", "target_id": "NPC_1", "on_interact_text": "Halt!"},
    )
    async with TestSessionLocal() as db:
        manifest = await AdventureExporter.build_full_manifest(db, adventure_id)
    async with TestSessionLocal() as db:
        await _delete_adventure(db, adventure_id)
        assert await AdventureTemplateImporter.import_adv_manifest(db, manifest, owner_id=user.id)
    async with TestSessionLocal() as db:
        imported = (await db.execute(select(AdventureTemplate))).scalars().first()
        imported_metadata = (await _npc_row(db, imported.id)).metadata_json
        re_exported = await AdventureExporter.build_full_manifest(db, imported.id)

    # Assert
    assert resp.status_code == 200, resp.text
    assert _exported_npc(manifest)["metadata_json"]["agent_runtime"] == AGENT_RUNTIME
    assert _exported_npc(manifest)["on_interact_text"] == "Halt!"
    assert imported_metadata["agent_runtime"] == AGENT_RUNTIME
    assert _exported_npc(re_exported)["metadata_json"]["agent_runtime"] == AGENT_RUNTIME
