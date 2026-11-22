"""Region Builder phase A: context options, requirements, id renames, gateways, preview.

Spec: docs/specs/region_builder.md (sections 5, 7, 8).
"""

from types import SimpleNamespace

import pytest
from sqlalchemy import select

from backend.api.routes.adventures.editing import section_generation
from backend.engine.world import section_generator
from backend.engine.world.section_context import normalize_context
from backend.engine.world.section_generator import (
    build_region_prompt,
    generate_section,
    normalize_settings,
)
from backend.engine.world.section_id_renames import rename_collisions
from backend.engine.world.section_prompt import id_prefix
from backend.engine.world.section_requirements import normalize_options, requirements_text
from backend.engine.world.section_validation import prepare_section, validate_section
from backend.engine.world.sections import normalize_sections
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.models.world_entity import WorldExit, WorldScene
from tests.conftest import TestSessionLocal
from tests.test_world_section_generation import (
    HARBOR,
    _FakeLLM,
    _ledger,
    _region,
    _seed_template,
)


def _blocks(prompt):
    return {b.id: b for b in prompt.blocks}


async def _prompt(settings=None):
    async with TestSessionLocal() as db:
        adv = await db.get(AdventureTemplate, "campaign")
        sections = normalize_sections(adv.world_sections)
        peaks = next(s for s in sections if s["id"] == "PEAKS")
        return await build_region_prompt(db, adv, peaks, sections, settings)


# --- settings --------------------------------------------------------------------------------


def test_settings_default_to_all_context_on():
    # Act
    settings = normalize_settings({"context": {"scenes": "nonsense", "npcs": "off"}})

    # Assert
    context = settings["context"]
    assert context["scenes"] == "compact" and context["npcs"] == "off"
    assert context["plot"] == "full" and context["walkthroughs"] is True
    assert settings["options"]["quest_generation_enabled"] is True
    assert normalize_context(None)["items"] == "compact"


def test_options_clamp_counts_and_word_the_requirements():
    # Arrange
    options = normalize_options(
        {
            "min_scenes": 12,
            "max_scenes": 4,
            "max_items": 500,
            "award_generation_enabled": False,
            "scripts_generation_enabled": False,
            "generation_strictness": "strict",
        }
    )

    # Act
    text = requirements_text(options)

    # Assert
    assert (options["min_scenes"], options["max_scenes"]) == (12, 12)
    assert options["max_items"] == 60
    assert "- New scenes: exactly 12." in text
    assert "- New awards: none." in text
    assert "Scripts: none" in text and "Strictness: strict" in text
    assert "typically 0 to 2" in text  # quests: the AI decides


def test_id_prefix_uses_initials_or_the_first_letters():
    assert id_prefix("GLOOM_PEAKS") == "GP_"
    assert id_prefix("PEAKS") == "PEA_"


# --- id renames ------------------------------------------------------------------------------


def test_colliding_ids_are_renamed_with_their_references():
    # Arrange
    region = _region(
        objects=[{"id": "KEY", "name": "Key", "description": "x", "start_scene_id": "HUT"}],
        scripts=[
            {
                "id": "HUT_ENTER",
                "trigger": "on_enter_scene",
                "target_id": "HUT",
                "code": "tw.player.give('KEY')",
            }
        ],
    )
    region["exits"][1]["item_to_unlock"] = "KEY"

    # Act
    notes = rename_collisions(region, _ledger())

    # Assert
    assert region["objects"][0]["id"] == "KEY_2"
    assert region["exits"][1]["item_to_unlock"] == "KEY_2"
    assert region["scripts"][0]["code"] == "tw.player.give('KEY_2')"
    assert region["exits"][0]["from_scene_id"] == "SQUARE"  # existing gateway stays
    assert notes == ["Renamed 'KEY' to 'KEY_2': the id already exists in the adventure."]


def test_a_region_reusing_an_existing_id_is_fixed_instead_of_rejected():
    # Arrange
    region = _region(
        objects=[{"id": "KEY", "name": "Key", "description": "x", "start_scene_id": "HUT"}]
    )

    # Act
    prepare_section(region, "PEAKS", _ledger())

    # Assert
    assert validate_section(region, _ledger(), ["HARBOR"]) == []


# --- context blocks --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_context_blocks_follow_the_chosen_options(setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange
        adv = await _seed_template(db)
        adv.plot = "The lighthouse went dark."
        adv.sequences = [
            {"id": "SEQ_1", "order": 1, "title": "Harbor", "walkthrough": "Ask the keeper."}
        ]
        db.add(WorldExit(template_id="campaign", from_scene_id="SQUARE", to_scene_id="SQUARE",
                         label="a gate", item_to_unlock="KEY"))  # fmt: skip
        await db.commit()

    # Act
    full = await _prompt()
    trimmed = await _prompt({"context": {"scenes": "off", "plot": "off", "walkthroughs": False}})

    # Assert
    text = full.user_prompt([])
    assert "- HARBOR: SQUARE (Square)" in text
    assert "KEY (Key, ITEM, in SQUARE) opens exit SQUARE -> SQUARE" in text
    assert "The lighthouse went dark." in text and "Ask the keeper." in text
    assert "CAMPAIGN OUTLINE" in text and "Id prefix of its new ids: PEA_" in text
    short = trimmed.user_prompt([])
    assert "EXISTING SCENES" not in short and "lighthouse" not in short
    assert "Ask the keeper." not in short and "1. Harbor" in short
    blocks = _blocks(trimmed)
    assert blocks["scenes"].included is False and blocks["scenes"].tokens > 0
    assert blocks["gateway"].always and "SQUARE (Square)" in blocks["gateway"].text
    assert trimmed.ledger.scene_ids == {"SQUARE"}  # validation keeps the full ledger


@pytest.mark.asyncio
async def test_gateways_prefer_border_scenes_and_fall_back_without_neighbours(setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange
        adv = await _seed_template(db)
        for scene_id in ("AAA_CELLAR", "ZZ_GATE"):
            db.add(WorldScene(id=scene_id, template_id="campaign", label=scene_id,
                              description="d", section_id="HARBOR"))  # fmt: skip
        db.add(WorldScene(id="WOODS", template_id="campaign", label="Woods", description="d"))
        db.add(WorldExit(template_id="campaign", from_scene_id="ZZ_GATE", to_scene_id="WOODS",
                         label="a road"))  # fmt: skip
        await db.commit()

        # Act
        with_link = await _prompt()
        adv = await db.get(AdventureTemplate, "campaign")
        sections = normalize_sections(adv.world_sections)
        lonely = {**next(s for s in sections if s["id"] == "PEAKS"), "planned_links": []}
        without_link = await build_region_prompt(db, adv, lonely, sections)

    # Assert
    gateway = _blocks(with_link)["gateway"].text.splitlines()
    assert gateway[1].startswith("Region HARBOR, travel_minutes 480")
    assert gateway[2].startswith("- ZZ_GATE")
    fallback = _blocks(without_link)["gateway"].text
    assert "no built neighbour" in fallback and "WOODS" in fallback


# --- generation and endpoints ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_generation_uses_the_settings(setup_test_db, monkeypatch):
    fake = _FakeLLM([_region()])
    monkeypatch.setattr(section_generator, "_llm", lambda _user: (fake, "model"))
    async with TestSessionLocal() as db:
        # Arrange
        await _seed_template(db)

        # Act
        await generate_section(
            db,
            "campaign",
            "PEAKS",
            None,
            {"context": {"scenes": "off"}, "options": {"max_scenes": 4}},
        )

    # Assert
    assert "EXISTING SCENES" not in fake.prompts[0]
    assert "- New scenes: at most 4." in fake.prompts[0]


async def _owned_template():
    async with TestSessionLocal() as db:
        adv = await _seed_template(db)
        adv.owner_id = (
            (await db.execute(select(User).where(User.username == "test_user"))).scalar_one().id
        )
        await db.commit()


@pytest.mark.asyncio
async def test_preview_endpoint_reports_blocks_and_tokens(auth_client, setup_test_db):
    # Arrange
    await _owned_template()

    # Act
    resp = await auth_client.post(
        "/api/adventures/campaign/editor/sections/PEAKS/generate/preview?include_prompt=true",
        json={"brief": "Ice and ruins.", "context": {"npcs": "off"}},
    )

    # Assert
    assert resp.status_code == 200, resp.text
    body = resp.json()
    blocks = {b["id"]: b for b in body["blocks"]}
    assert blocks["system"]["always"] and blocks["gateway"]["always"]
    assert blocks["npcs"]["included"] is False and blocks["npcs"]["empty"] is True
    assert body["total_tokens"] == sum(b["tokens"] for b in body["blocks"] if b["included"])
    assert "Brief: Ice and ruins." in body["prompt"]


@pytest.mark.asyncio
async def test_generate_endpoint_hands_the_settings_to_the_job(
    auth_client, setup_test_db, monkeypatch
):
    captured = {}

    async def _job(template_id, section_id, user_id, settings=None):
        captured.update(settings=settings, section=section_id)

    monkeypatch.setattr(section_generation, "run_generation", _job)
    monkeypatch.setattr(section_generation, "_RUNNING", {})
    await _owned_template()

    # Act
    resp = await auth_client.post(
        "/api/adventures/campaign/editor/sections/PEAKS/generate",
        json={"brief": "Ice.", "context": {"items": "full"}, "options": {"min_quests": 1}},
    )
    await section_generation._RUNNING[("campaign", "PEAKS")]

    # Assert
    assert resp.status_code == 202, resp.text
    assert captured["section"] == "PEAKS"
    assert captured["settings"]["context"]["items"] == "full"
    assert captured["settings"]["options"]["min_quests"] == 1


@pytest.mark.asyncio
async def test_old_request_body_still_works(auth_client, setup_test_db, monkeypatch):
    async def _job(*_args, **_kwargs):
        return None

    monkeypatch.setattr(section_generation, "run_generation", _job)
    monkeypatch.setattr(section_generation, "_RUNNING", {})
    await _owned_template()

    # Act
    resp = await auth_client.post(
        "/api/adventures/campaign/editor/sections/PEAKS/generate", json={"brief": "Ice."}
    )

    # Assert
    assert resp.status_code == 202, resp.text
    assert SimpleNamespace(**resp.json()).status == "generating"


@pytest.mark.asyncio
async def test_the_region_keeps_its_builder_settings_but_sessions_never_see_them(
    auth_client, setup_test_db, monkeypatch
):
    from backend.engine.world.sections import player_sections

    async def _job(*_args, **_kwargs):
        return None

    monkeypatch.setattr(section_generation, "run_generation", _job)
    monkeypatch.setattr(section_generation, "_RUNNING", {})
    await _owned_template()

    # Act
    resp = await auth_client.post(
        "/api/adventures/campaign/editor/sections/PEAKS/generate",
        json={"brief": "Ice.", "mode": "advanced", "context": {"scenes": "full"}},
    )

    # Assert
    assert resp.status_code == 202, resp.text
    async with TestSessionLocal() as db:
        adv = await db.get(AdventureTemplate, "campaign")
    peaks = next(s for s in normalize_sections(adv.world_sections) if s["id"] == "PEAKS")
    stored = peaks["generation_settings"]
    assert stored["mode"] == "advanced" and stored["context"]["scenes"] == "full"
    assert stored["options"]["quest_generation_enabled"] is True
    built = [{**peaks, "status": "built"}]
    assert "generation_settings" not in player_sections(built)[0]


@pytest.mark.asyncio
async def test_gateway_scenes_picked_by_the_author_come_first(setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange
        await _seed_template(db)
        db.add(WorldScene(id="ZZ_GATE", template_id="campaign", label="Gate", description="d",
                          section_id="HARBOR"))  # fmt: skip
        await db.commit()
        adv = await db.get(AdventureTemplate, "campaign")
        sections = normalize_sections(adv.world_sections)
        peaks = next(s for s in sections if s["id"] == "PEAKS")
        peaks["planned_links"][0]["gateway_scene_ids"] = ["ZZ_GATE", "GONE"]

        # Act
        prompt = await build_region_prompt(db, adv, peaks, sections)

    # Assert
    lines = _blocks(prompt)["gateway"].text.splitlines()
    assert lines[2].startswith("- ZZ_GATE") and lines[3].startswith("- SQUARE")
    assert normalize_sections([HARBOR, PEAKS_LINKED])[1]["planned_links"][0][
        "gateway_scene_ids"
    ] == ["ZZ_GATE"]


PEAKS_LINKED = {
    "id": "PEAKS",
    "label": "Peaks",
    "planned_links": [{"to_section_id": "HARBOR", "gateway_scene_ids": [" zz_gate ", "ZZ_GATE"]}],
}


@pytest.mark.asyncio
async def test_preview_uses_unsaved_gateway_picks(auth_client, setup_test_db):
    # Arrange
    await _owned_template()
    async with TestSessionLocal() as db:
        db.add(WorldScene(id="ZZ_GATE", template_id="campaign", label="Gate", description="d",
                          section_id="HARBOR"))  # fmt: skip
        await db.commit()

    # Act
    resp = await auth_client.post(
        "/api/adventures/campaign/editor/sections/PEAKS/generate/preview?include_prompt=true",
        json={"gateways": {"HARBOR": ["ZZ_GATE"]}},
    )

    # Assert
    assert resp.status_code == 200, resp.text
    prompt = resp.json()["prompt"]
    assert prompt.index("- ZZ_GATE") < prompt.index("- SQUARE (Square):")
