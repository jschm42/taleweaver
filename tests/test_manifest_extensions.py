"""Top-level ``extensions`` block: fork-specific manifest data survives import and export."""

import io
import json
import zipfile

import pytest
from sqlalchemy import select

from backend.core.manifest_extensions import (
    MAX_EXTENSIONS_BYTES,
    MAX_NAMESPACES,
    normalize_extensions,
)
from backend.engine.adventures.adventure_exporter import AdventureExporter
from backend.engine.adventures.adventure_importer import AdventureTemplateImporter
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from tests.conftest import TestSessionLocal
from tests.test_adventure_lifecycle import (
    _delete_adventure,
    _patch_export_filesystem,
    _patch_import_filesystem,
    _seed_adventure,
)

EXTENSIONS = {
    "vn_fork": {"mode": "visual_novel", "portraits": {"NPC_GUARD": "assets/guard.png"}},
    "comfyui": {"checkpoint": "illustrious-xl", "steps": 28},
}


def test_normalize_keeps_valid_namespaces():
    # Arrange
    raw = {**EXTENSIONS, "acme.tools-v2": {"x": 1}}

    # Act
    result = normalize_extensions(raw)

    # Assert
    assert result == raw


def test_normalize_drops_invalid_entries():
    # Arrange
    raw = {
        "Bad Name": {"x": 1},
        "_leading": {"x": 1},
        "not_an_object": [1, 2],
        "scalar": "text",
        "ok": {"x": 1},
    }

    # Act
    result = normalize_extensions(raw)

    # Assert
    assert result == {"ok": {"x": 1}}


def test_normalize_rejects_non_dict_block():
    # Arrange / Act / Assert
    assert normalize_extensions(["vn_fork"]) == {}
    assert normalize_extensions(None) == {}


def test_normalize_caps_namespaces_and_size():
    # Arrange
    many = {f"ns{i}": {"i": i} for i in range(MAX_NAMESPACES + 5)}
    huge = {"big": {"blob": "x" * MAX_EXTENSIONS_BYTES}, "small": {"x": 1}}

    # Act
    capped = normalize_extensions(many)
    sized = normalize_extensions(huge)

    # Assert
    assert len(capped) == MAX_NAMESPACES
    assert sized == {"small": {"x": 1}}


async def _seed_with_extensions(db, user_id: str) -> str:
    adventure_id = await _seed_adventure(db, user_id)
    adv = await db.get(AdventureTemplate, adventure_id)
    adv.original_manifest = {"extensions": {**EXTENSIONS, "Invalid Key": {"x": 1}}}
    await db.commit()
    return adventure_id


@pytest.mark.asyncio
async def test_export_omits_empty_extensions(auth_client, setup_test_db):
    # Arrange
    async with TestSessionLocal() as db:
        user = (await db.execute(select(User).limit(1))).scalars().first()
        adventure_id = await _seed_adventure(db, user.id)

    # Act
    async with TestSessionLocal() as db:
        manifest = await AdventureExporter.build_full_manifest(db, adventure_id)

    # Assert
    assert "extensions" not in manifest


@pytest.mark.asyncio
async def test_extensions_survive_adv_round_trip(auth_client, setup_test_db):
    # Arrange
    async with TestSessionLocal() as db:
        user = (await db.execute(select(User).limit(1))).scalars().first()
        adventure_id = await _seed_with_extensions(db, user.id)

    # Act
    async with TestSessionLocal() as db:
        manifest = await AdventureExporter.build_full_manifest(db, adventure_id)
    async with TestSessionLocal() as db:
        await _delete_adventure(db, adventure_id)
        assert await AdventureTemplateImporter.import_adv_manifest(db, manifest, owner_id=user.id)
    async with TestSessionLocal() as db:
        imported = (await db.execute(select(AdventureTemplate))).scalars().first()
        re_exported = await AdventureExporter.build_full_manifest(db, imported.id)

    # Assert
    assert manifest["extensions"] == EXTENSIONS
    assert re_exported["extensions"] == EXTENSIONS


@pytest.mark.asyncio
async def test_extensions_survive_adz_round_trip(auth_client, setup_test_db, monkeypatch):
    # Arrange
    async with TestSessionLocal() as db:
        user = (await db.execute(select(User).limit(1))).scalars().first()
        adventure_id = await _seed_with_extensions(db, user.id)

    # Act
    _patch_export_filesystem(monkeypatch)
    async with TestSessionLocal() as db:
        adz_bytes = await AdventureExporter.export_adz(db, adventure_id)
    with zipfile.ZipFile(io.BytesIO(adz_bytes)) as z:
        exported = json.loads(z.read("adventure.adv"))
    _patch_import_filesystem(monkeypatch)
    async with TestSessionLocal() as db:
        await _delete_adventure(db, adventure_id)
        assert await AdventureTemplateImporter.import_adz(db, adz_bytes, owner_id=user.id)
    async with TestSessionLocal() as db:
        imported = (await db.execute(select(AdventureTemplate))).scalars().first()

    # Assert
    assert exported["extensions"] == EXTENSIONS
    assert imported.original_manifest["extensions"] == EXTENSIONS
