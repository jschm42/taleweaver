"""Narrator voices: admin catalog, adventure field, manifest round trip and narration prompt."""

import pytest
from sqlalchemy import select

from backend.core.narrator_voices import (
    DEFAULT_NARRATOR_VOICES,
    narrator_voice_rules,
    normalize_voice,
    normalize_voice_catalog,
)
from backend.engine.adventures.adventure_exporter import AdventureExporter
from backend.engine.adventures.adventure_importer import AdventureTemplateImporter
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from tests.test_adventure_lifecycle import _delete_adventure, _seed_adventure

NOIR = {
    "id": "noir-detective",
    "name": "Hardboiled Noir Detective",
    "instruction": "Narrate dry and cynical.",
    "sample": "Rain hit the neon sign like cheap static.",
}


def test_defaults_offer_ten_voices_with_unique_ids():
    # Act
    ids = [voice["id"] for voice in DEFAULT_NARRATOR_VOICES]

    # Assert
    assert len(ids) == 10
    assert len(set(ids)) == 10
    assert all(voice["instruction"] and voice["sample"] for voice in DEFAULT_NARRATOR_VOICES)


def test_catalog_drops_broken_and_duplicate_entries_and_falls_back_to_defaults():
    # Arrange
    raw = [NOIR, {**NOIR, "name": "Copy"}, {"name": "No instruction"}, "junk"]

    # Act
    catalog = normalize_voice_catalog(raw)

    # Assert
    assert [voice["name"] for voice in catalog] == ["Hardboiled Noir Detective"]
    assert normalize_voice_catalog([]) == normalize_voice_catalog(None)
    assert len(normalize_voice_catalog([])) == len(DEFAULT_NARRATOR_VOICES)


def test_custom_voice_without_name_gets_a_label():
    # Act
    voice = normalize_voice({"id": "custom", "instruction": "  Speak   like a pirate. "})

    # Assert
    assert voice == {
        "id": "custom",
        "name": "Custom",
        "description": "",
        "instruction": "Speak like a pirate.",
        "sample": "",
    }


def test_rules_carry_instruction_and_sample_and_keep_length_rules_in_charge():
    # Act
    rules = narrator_voice_rules(NOIR)

    # Assert
    assert rules.startswith("NARRATOR VOICE — HARDBOILED NOIR DETECTIVE: Narrate dry and cynical.")
    assert '"Rain hit the neon sign like cheap static."' in rules
    assert "never overrides the length rules" in rules
    assert narrator_voice_rules(None) == ""
    assert narrator_voice_rules({"name": "Empty"}) == ""


@pytest.mark.asyncio
async def test_catalog_api_returns_defaults_and_saves_admin_changes(auth_client, setup_test_db):
    # Act
    initial = (await auth_client.get("/api/settings/narrator-voices")).json()
    saved = await auth_client.post("/api/settings/narrator-voices", json={"items": [NOIR]})
    reloaded = (await auth_client.get("/api/settings/narrator-voices")).json()

    # Assert
    assert len(initial["items"]) == len(DEFAULT_NARRATOR_VOICES)
    assert saved.status_code == 200
    assert [voice["id"] for voice in reloaded["items"]] == ["noir-detective"]
    assert len(reloaded["defaults"]) == len(DEFAULT_NARRATOR_VOICES)


@pytest.mark.asyncio
async def test_editor_patch_stores_and_clears_the_voice(auth_client, setup_test_db):
    from tests.conftest import TestSessionLocal

    # Arrange
    async with TestSessionLocal() as db:
        user = (await db.execute(select(User).limit(1))).scalars().first()
        adventure_id = await _seed_adventure(db, user.id)
    custom = {"id": "custom", "name": "Custom", "instruction": "Speak like a pirate."}

    # Act
    stored = await auth_client.patch(
        f"/api/adventures/{adventure_id}", json={"narrator_voice": custom}
    )
    cleared = await auth_client.patch(
        f"/api/adventures/{adventure_id}", json={"narrator_voice": None}
    )

    # Assert
    assert stored.status_code == 200
    assert stored.json()["narrator_voice"]["instruction"] == "Speak like a pirate."
    assert cleared.json()["narrator_voice"] is None


@pytest.mark.asyncio
async def test_voice_survives_adv_export_import(auth_client, setup_test_db):
    from tests.conftest import TestSessionLocal

    # Arrange
    async with TestSessionLocal() as db:
        user = (await db.execute(select(User).limit(1))).scalars().first()
        adventure_id = await _seed_adventure(db, user.id)
        adv = await db.get(AdventureTemplate, adventure_id)
        adv.narrator_voice = normalize_voice(NOIR)
        await db.commit()

    # Act
    async with TestSessionLocal() as db:
        manifest = await AdventureExporter.build_full_manifest(db, adventure_id)
    async with TestSessionLocal() as db:
        await _delete_adventure(db, adventure_id)
        assert await AdventureTemplateImporter.import_adv_manifest(db, manifest, owner_id=user.id)
        imported = (await db.execute(select(AdventureTemplate))).scalars().first()

    # Assert
    assert manifest["adventure"]["narrator_voice"]["id"] == "noir-detective"
    assert imported.narrator_voice == normalize_voice(NOIR)
