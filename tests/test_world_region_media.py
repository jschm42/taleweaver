"""Region Builder phase D: images and voices, validate & fix, discard region.

Spec: docs/specs/region_builder.md (7.3, phase D).
"""

from types import SimpleNamespace

import pytest
from sqlalchemy import select

from backend.api.routes.adventures.editing import auto_fix, section_generation
from backend.engine.manifest_apply.context import ApplyContext
from backend.engine.manifest_apply.section_media import RegionMedia, enable_images, image_notes
from backend.engine.world import section_generator
from backend.engine.world.section_generator import generate_section
from backend.engine.world.section_requirements import normalize_options, requirements_text
from backend.engine.world.sections import normalize_sections, player_sections
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene
from tests.conftest import TestSessionLocal
from tests.test_world_section_generation import _FakeLLM, _region, _seed_template


def _peaks(adv):
    return next(s for s in normalize_sections(adv.world_sections) if s["id"] == "PEAKS")


# --- images and voices -----------------------------------------------------------------------


def test_media_options_default_to_no_images_but_voices():
    # Act
    options = normalize_options({})

    # Assert
    assert options["generate_scene_images"] is False
    assert options["automatic_npc_voice_assignment"] is True
    assert options["auto_validate_and_fix"] is False
    assert "NPC VOICES" not in requirements_text(
        normalize_options({"automatic_npc_voice_assignment": False})
    )


def test_voice_list_is_limited_to_new_characters(monkeypatch):
    from backend.engine.world import world_prompt_builder

    monkeypatch.setattr(world_prompt_builder, "load_voice_catalog", lambda: [_VOICE])

    # Act
    text = requirements_text(normalize_options({}))

    # Assert
    assert "NPC VOICES" in text and "only the NEW characters" in text


_VOICE = {
    "id": "v1",
    "name": "Ada",
    "gender": "female",
    "age": "old",
    "accent": "",
    "description": "warm",
    "good_for": [],
}


def test_images_are_skipped_with_a_note_when_not_set_up():
    # Arrange
    user = SimpleNamespace(t2i_settings={}, encrypted_api_keys={}, image_styles_catalog=None)
    ctx = ApplyContext(db=None, template_id="t", manifest={}, user=user, adventure=None)

    # Act
    notes = enable_images(ctx, RegionMedia(scenes=True))

    # Assert
    assert notes and notes[0].startswith("Images skipped:")
    assert ctx.gen_scenes is False and image_notes(ctx) == []


def test_failed_and_blocked_images_become_notes():
    # Arrange
    ctx = ApplyContext(db=None, template_id="t", manifest={}, user=None, adventure=None)
    ctx.gen_npc = True
    ctx.image_counters.update(attempts=4, successes=1, moderation=1)

    # Act
    notes = image_notes(ctx)

    # Assert
    assert any("blocked by safety filters" in n for n in notes)
    assert any("2 image(s) could not be generated" in n for n in notes)


# --- generated record and discard ------------------------------------------------------------


async def _build_peaks(monkeypatch) -> None:
    fake = _FakeLLM([_region()])
    monkeypatch.setattr(section_generator, "_llm", lambda _user: (fake, "model"))
    async with TestSessionLocal() as db:
        await _seed_template(db)
        await generate_section(db, "campaign", "PEAKS", None)


@pytest.mark.asyncio
async def test_a_built_region_records_what_it_added(setup_test_db, monkeypatch):
    # Act
    await _build_peaks(monkeypatch)

    # Assert
    async with TestSessionLocal() as db:
        adv = await db.get(AdventureTemplate, "campaign")
    record = _peaks(adv)["generated"]
    assert set(record["scene_ids"]) == {"PASS", "HUT"}
    assert set(record["entity_ids"]) == {"HERMIT", "RUNE"}
    assert record["quest_ids"] == ["Q_HERMIT"] and record["sequence_ids"] == ["SEQ_PEAKS"]
    assert record["planned_links"][0]["to_section_id"] == "HARBOR"
    assert "generated" not in player_sections(adv.world_sections)[0]


@pytest.mark.asyncio
async def test_discard_takes_the_region_out_and_plans_it_again(setup_test_db, monkeypatch):
    from backend.engine.manifest_apply.section_discard import discard_section

    # Arrange
    await _build_peaks(monkeypatch)

    # Act
    async with TestSessionLocal() as db:
        removed = await discard_section(db, "campaign", "PEAKS")

    # Assert
    assert removed["scenes"] == 2 and removed["entities"] == 2 and removed["exits"] == 2
    async with TestSessionLocal() as db:
        adv = await db.get(AdventureTemplate, "campaign")
        scenes = {s.id for s in (await db.execute(select(WorldScene))).scalars().all()}
        exits = (await db.execute(select(WorldExit))).scalars().all()
        entities = {e.id for e in (await db.execute(select(WorldEntity))).scalars().all()}
    peaks = _peaks(adv)
    assert scenes == {"SQUARE"} and exits == [] and entities == {"KEY"}
    assert peaks["status"] == "stub" and peaks["generated"] is None
    assert peaks["planned_links"][0]["travel_minutes"] == 480
    assert adv.quests == [] and [s["order"] for s in adv.sequences] == [1]
    assert {s["id"] for s in adv.original_manifest["scenes"]} == {"SQUARE"}


async def _owned_template():
    async with TestSessionLocal() as db:
        adv = await _seed_template(db)
        adv.owner_id = (
            (await db.execute(select(User).where(User.username == "test_user"))).scalar_one().id
        )
        await db.commit()


@pytest.mark.asyncio
async def test_a_region_not_built_by_the_builder_cannot_be_discarded(auth_client, setup_test_db):
    # Arrange
    await _owned_template()

    # Act
    resp = await auth_client.post("/api/adventures/campaign/editor/sections/HARBOR/discard")

    # Assert
    assert resp.status_code == 409
    assert "Region Builder" in resp.json()["detail"]


# --- validate & fix --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_and_fix_only_touches_the_new_findings(setup_test_db, monkeypatch):
    seen = {}

    async def _generated(*_args, **_kwargs):
        return []

    async def _findings(*_args, **_kwargs):
        return {"old": object()}

    async def _fix(_db, _template_id, _user, include_ai=True, skip_signatures=None):
        seen.update(include_ai=include_ai, skip=skip_signatures)
        return SimpleNamespace(fixed=1, findings_total=2)

    monkeypatch.setattr(section_generation, "generate_section", _generated)
    monkeypatch.setattr(section_generation, "_findings", _findings)
    monkeypatch.setattr(section_generation, "session_factory", lambda: TestSessionLocal)
    monkeypatch.setattr(auto_fix, "run_post_generation_auto_fix", _fix)
    async with TestSessionLocal() as db:
        await _seed_template(db)

    # Act
    await section_generation.run_generation(
        "campaign", "PEAKS", "nobody", {"options": {"auto_validate_and_fix": True}}
    )

    # Assert
    assert seen == {"include_ai": False, "skip": {"old"}}
    async with TestSessionLocal() as db:
        adv = await db.get(AdventureTemplate, "campaign")
    assert "Validate & fix: 1 of 2 new finding(s) fixed." in _peaks(adv)["generation_notes"]
