"""Region Builder phase C: a blueprint in the region idea (docs/specs/region_builder.md, 6)."""

import pytest
from sqlalchemy import select

from backend.api.routes.adventures.editing import section_generation
from backend.engine.blueprint.region_mode import RegionWorld, analyze_region_blueprint
from backend.engine.world import section_generator
from backend.engine.world.section_generator import generate_section
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene
from tests.conftest import TestSessionLocal
from tests.test_world_section_generation import _FakeLLM, _region, _seed_template

WORLD = RegionWorld(
    section_id="PEAKS",
    taken_ids={"SQUARE", "KEY", "HARBORMASTER"},
    scene_ids={"SQUARE", "MINE_GATE"},
    scene_sections={"SQUARE": "HARBOR", "MINE_GATE": "MINES"},
    linked_section_ids={"HARBOR"},
)

BLUEPRINT = """Frozen dwarven ruins above the harbor.

[World] Ignored
Tone: Horror

[Scene: PASS] Windy Pass
A narrow pass.

[Exit: SQUARE -> PASS] the high road
Travel: 8h

[Item: RUNE] Glowing rune
Scene: PASS
Unlocks: KEY

[Sequence: 1] Into the peaks
Goal: Reach the hut.
"""


def _messages(result, severity):
    return [i.message for i in result.blueprint.issues if i.severity == severity]


# --- region mode -----------------------------------------------------------------------------


def test_region_mode_drops_global_blocks_and_accepts_existing_references():
    # Act
    result = analyze_region_blueprint(BLUEPRINT, WORLD)

    # Assert
    assert result is not None and result.errors == []
    assert result.premise.startswith("Frozen dwarven ruins")
    assert "world" not in result.kinds() and result.kinds()["scene"] == 1
    assert any("is global to the adventure" in m for m in _messages(result, "warning"))
    assert "SQUARE" not in result.missing_ids
    assert not any("SQUARE" in m for m in _messages(result, "warning"))
    assert "REGION BLUEPRINT NOTES" in result.prompt_section("creative")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("[NPC: HARBORMASTER] Old Vell\nScene: PASS\n", "exists already"),
        ("[Scene: PASS] Pass\nSection: HARBOR\n", "belongs to HARBOR"),
        ("[Exit: SQUARE -> MINE_GATE] a tunnel\n", "only joins existing scenes"),
    ],
)
def test_region_mode_errors(text, expected):
    # Act
    result = analyze_region_blueprint(text, WORLD)

    # Assert
    assert any(expected in e for e in result.errors), result.errors


def test_an_exit_into_an_unlinked_region_is_a_warning():
    # Act
    result = analyze_region_blueprint(
        "[Scene: PASS] Pass\n\n[Exit: PASS -> MINE_GATE] a tunnel\n", WORLD
    )

    # Assert
    assert result.errors == []
    assert any("not in a linked region" in m for m in _messages(result, "warning"))


def test_a_region_without_links_may_use_any_existing_scene():
    # Arrange
    world = RegionWorld(**{**WORLD.__dict__, "linked_section_ids": set()})

    # Act
    result = analyze_region_blueprint(
        "[Scene: PASS] Pass\n\n[Exit: PASS -> MINE_GATE] a tunnel\n", world
    )

    # Assert
    assert result.blueprint.issues == []


def test_plain_text_is_no_blueprint():
    assert analyze_region_blueprint("Just ice and ruins.", WORLD) is None


# --- generation and endpoints ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_blueprint_shapes_the_generated_region(setup_test_db, monkeypatch):
    fake = _FakeLLM([_region()])
    monkeypatch.setattr(section_generator, "_llm", lambda _user: (fake, "model"))
    async with TestSessionLocal() as db:
        # Arrange
        adv = await _seed_template(db)
        adv.world_sections = [
            {**s, "brief": BLUEPRINT} if s["id"] == "PEAKS" else s for s in adv.world_sections
        ]
        await db.commit()

        # Act
        notes = await generate_section(db, "campaign", "PEAKS", None)

    # Assert
    prompt = fake.prompts[0]
    assert "Brief: Frozen dwarven ruins above the harbor." in prompt
    assert '"id": "PASS"' in prompt and "Tone: Horror" not in prompt
    async with TestSessionLocal() as db:
        scenes = {s.id: s for s in (await db.execute(select(WorldScene))).scalars().all()}
        exits = (await db.execute(select(WorldExit))).scalars().all()
        adv = await db.get(AdventureTemplate, "campaign")
        rune = (await db.execute(select(WorldEntity).where(WorldEntity.id == "RUNE"))).scalar_one()
    assert scenes["PASS"].label == "Windy Pass"
    assert any(e.from_scene_id == "SQUARE" and e.travel_minutes == 480 for e in exits)
    assert [s["order"] for s in adv.sequences] == [1, 2]
    assert adv.sequences[1]["title"] == "Into the peaks"
    assert rune.name == "Glowing rune" and isinstance(notes, list)


async def _owned_template():
    async with TestSessionLocal() as db:
        adv = await _seed_template(db)
        adv.owner_id = (
            (await db.execute(select(User).where(User.username == "test_user"))).scalar_one().id
        )
        await db.commit()


@pytest.mark.asyncio
async def test_preview_reports_the_blueprint(auth_client, setup_test_db):
    # Arrange
    await _owned_template()

    # Act
    resp = await auth_client.post(
        "/api/adventures/campaign/editor/sections/PEAKS/generate/preview",
        json={"brief": BLUEPRINT},
    )

    # Assert
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["blueprint"]["kinds"]["scene"] == 1
    assert any(i["severity"] == "warning" for i in body["blueprint"]["issues"])
    assert next(b for b in body["blocks"] if b["id"] == "blueprint")["tokens"] > 0


@pytest.mark.asyncio
async def test_a_blueprint_with_errors_is_refused(auth_client, setup_test_db, monkeypatch):
    async def _job(*_args, **_kwargs):
        return None

    monkeypatch.setattr(section_generation, "run_generation", _job)
    monkeypatch.setattr(section_generation, "_RUNNING", {})
    await _owned_template()

    # Act
    resp = await auth_client.post(
        "/api/adventures/campaign/editor/sections/PEAKS/generate",
        json={"brief": "[Scene: SQUARE] Again\n"},
    )

    # Assert
    assert resp.status_code == 400
    assert "exists already" in resp.json()["detail"]
