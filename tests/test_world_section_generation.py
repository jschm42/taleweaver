"""Region generation, planning and session expansion (docs/specs/world_sections.md, phase 3)."""

from types import SimpleNamespace

import pytest
from sqlalchemy import select

from backend.api.routes.adventures.editing import section_generation
from backend.api.routes.adventures.session_adventure import build_session_snapshot
from backend.api.routes.adventures.session_expansion import expand_session, pending_sections
from backend.engine.world import section_generator
from backend.engine.world.section_generator import SectionGenerationError, generate_section
from backend.engine.world.section_ledger import Ledger, build_ledger
from backend.engine.world.section_validation import prepare_section, validate_section
from backend.engine.world.sections import normalize_sections
from backend.models.adventure_template import AdventureTemplate
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene
from tests.conftest import TestSessionLocal

HARBOR = {"id": "HARBOR", "label": "Harbor", "description": "A port.", "status": "built"}
PEAKS = {
    "id": "PEAKS",
    "label": "Peaks",
    "description": "Cold mountains.",
    "status": "stub",
    "brief": "Dwarven ruins.",
    "planned_links": [{"to_section_id": "HARBOR", "travel_minutes": 480}],
}


def _region(**overrides):
    region = {
        "summary": "A mountain pass with a dwarven hermit.",
        "scenes": [
            {"id": "PASS", "name": "Pass", "description": "Wind."},
            {"id": "HUT", "name": "Hut", "description": "Smoke.", "is_fast_travel_point": True},
        ],
        "exits": [
            {"from_scene_id": "SQUARE", "to_scene_id": "PASS", "label": "the high road",
             "exit_type": "bidirectional", "travel_minutes": 480},
            {"from_scene_id": "PASS", "to_scene_id": "HUT", "label": "a trail",
             "exit_type": "bidirectional"},
        ],
        "npcs": [{"id": "HERMIT", "name": "Hermit", "description": "Old.", "start_scene_id": "HUT"}],
        "objects": [{"id": "RUNE", "name": "Rune", "description": "Glows.", "start_scene_id": "HUT"}],
        "quests": [{"id": "Q_HERMIT", "title": "The Hermit", "description": "Help him."}],
        "awards": [],
        "sequences": [{"id": "SEQ_PEAKS", "order": 1, "title": "The Peaks"}],
        "scripts": [{"id": "BOOT", "trigger": "on_init", "code": "pass"}],
    }  # fmt: skip
    region.update(overrides)
    return region


def _ledger(**overrides):
    values = {
        "scene_ids": {"SQUARE"},
        "entity_ids": {"KEY"},
        "item_ids": {"KEY"},
        "sequence_orders": {1, 2},
        "scene_sections": {"SQUARE": "HARBOR"},
    }
    values.update(overrides)
    return Ledger(**values)


# --- validation ------------------------------------------------------------------------------


def test_prepare_section_fixes_regions_chapters_and_init_scripts():
    # Arrange
    region = _region()

    # Act
    notes = prepare_section(region, "PEAKS", _ledger())

    # Assert
    assert {s["section_id"] for s in region["scenes"]} == {"PEAKS"}
    assert region["sequences"][0]["order"] == 3
    assert region["scripts"] == [] and notes


def test_a_valid_region_passes():
    # Act / Assert
    assert validate_section(_region(), _ledger(), ["HARBOR"]) == []


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"scenes": []}, "no scenes"),
        ({"objects": [{"id": "KEY", "name": "Key", "description": "x", "start_scene_id": "HUT"}]},
         "already exists"),
        ({"exits": [{"from_scene_id": "PASS", "to_scene_id": "HUT", "exit_type": "bidirectional"}]},
         "No exit connects the region"),
        ({"exits": [{"from_scene_id": "SQUARE", "to_scene_id": "PASS", "exit_type": "bidirectional"}]},
         "'HUT' cannot be reached"),
        ({"npcs": [{"id": "HERMIT", "name": "H", "description": "x", "start_scene_id": "SQUARE"}]},
         "not a new scene"),
        ({"scripts": [{"id": "BAD", "trigger": "on_enter_scene", "code": "def ("}]}, "Script 'BAD'"),
    ],
)  # fmt: skip
def test_invalid_regions_are_rejected(overrides, expected):
    # Act
    errors = validate_section(_region(**overrides), _ledger(), [])

    # Assert
    assert any(expected in error for error in errors), errors


def test_a_planned_neighbour_must_be_connected():
    # Arrange
    ledger = _ledger(
        scene_ids={"SQUARE", "CAVE"}, scene_sections={"SQUARE": "HARBOR", "CAVE": "MINES"}
    )

    # Act
    errors = validate_section(_region(), ledger, ["HARBOR", "MINES"])

    # Assert
    assert errors == ["No exit connects the region to the neighbouring region MINES."]


# --- generation ------------------------------------------------------------------------------


async def _seed_template(db) -> AdventureTemplate:
    user = (await db.execute(select(User).limit(1))).scalars().first()
    adv = AdventureTemplate(
        id="campaign",
        title="Campaign",
        owner_id=user.id if user else None,
        world_sections=normalize_sections([HARBOR, PEAKS]),
        sequences=[{"id": "SEQ_1", "order": 1, "title": "Harbor"}],
        quests=[],
        awards=[],
        original_manifest={"scenes": [{"id": "SQUARE"}], "sections": []},
    )
    db.add(adv)
    db.add(
        WorldScene(
            id="SQUARE",
            template_id="campaign",
            label="Square",
            description="d",
            section_id="HARBOR",
        )
    )
    db.add(WorldEntity(id="KEY", template_id="campaign", entity_type="OBJECT", name="Key",
                       description="Old.", current_scene_id="SQUARE"))  # fmt: skip
    await db.commit()
    return adv


@pytest.mark.asyncio
async def test_ledger_lists_existing_content_by_region(setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange
        adv = await _seed_template(db)
        db.add(WorldExit(template_id="campaign", from_scene_id="SQUARE", to_scene_id="SQUARE",
                         label="a gate", item_to_unlock="KEY"))  # fmt: skip
        await db.commit()

        # Act
        ledger = await build_ledger(db, adv)

    # Assert
    assert ledger.taken_ids >= {"SQUARE", "KEY"} and ledger.sequence_orders == {1}
    assert ledger.scenes_of("HARBOR") == ["SQUARE"]
    assert ledger.item_ids == {"KEY"}


class _FakeLLM:
    def __init__(self, results):
        self.results = list(results)
        self.prompts: list[str] = []

    async def aexecute_complex_task(self, **kwargs):
        self.prompts.append(kwargs["user_prompt"])
        result = self.results.pop(0)
        return SimpleNamespace(model_dump=lambda: result)


@pytest.mark.asyncio
async def test_generation_retries_once_and_merges_the_region(setup_test_db, monkeypatch):
    fake = _FakeLLM([_region(scenes=[]), _region()])
    monkeypatch.setattr(section_generator, "_llm", lambda _user: (fake, "model"))
    async with TestSessionLocal() as db:
        # Arrange
        await _seed_template(db)

        # Act
        await generate_section(db, "campaign", "PEAKS", None)

    # Assert
    assert "YOUR LAST ATTEMPT WAS REJECTED" in fake.prompts[1] and "Square" in fake.prompts[0]
    async with TestSessionLocal() as db:
        adv = await db.get(AdventureTemplate, "campaign")
        scenes = {s.id: s for s in (await db.execute(select(WorldScene))).scalars().all()}
        exits = (await db.execute(select(WorldExit))).scalars().all()
        hermit = (
            await db.execute(select(WorldEntity).where(WorldEntity.id == "HERMIT"))
        ).scalar_one()
    peaks = next(s for s in adv.world_sections if s["id"] == "PEAKS")
    assert peaks["status"] == "built" and peaks["summary"].startswith("A mountain pass")
    assert scenes["HUT"].section_id == "PEAKS" and scenes["HUT"].is_fast_travel_point is True
    assert any(e.travel_minutes == 480 for e in exits)
    assert hermit.current_scene_id == "HUT"
    assert [q["id"] for q in adv.quests] == ["Q_HERMIT"]
    assert [s["order"] for s in adv.sequences] == [1, 2]
    assert {s["id"] for s in adv.original_manifest["scenes"]} == {"SQUARE", "PASS", "HUT"}


@pytest.mark.asyncio
async def test_a_region_that_stays_invalid_changes_nothing(setup_test_db, monkeypatch):
    fake = _FakeLLM([_region(scenes=[]), _region(scenes=[])])
    monkeypatch.setattr(section_generator, "_llm", lambda _user: (fake, "model"))
    async with TestSessionLocal() as db:
        # Arrange
        await _seed_template(db)

        # Act / Assert
        with pytest.raises(SectionGenerationError):
            await generate_section(db, "campaign", "PEAKS", None)
        count = len((await db.execute(select(WorldScene))).scalars().all())
    assert count == 1


@pytest.mark.asyncio
async def test_failed_background_generation_marks_the_region_planned_again(
    setup_test_db, monkeypatch
):
    async def _fail(*_args, **_kwargs):
        raise SectionGenerationError(["The region has no scenes."])

    monkeypatch.setattr(section_generation, "generate_section", _fail)
    monkeypatch.setattr(section_generation, "session_factory", lambda: TestSessionLocal)
    async with TestSessionLocal() as db:
        # Arrange
        await _seed_template(db)
        user = (await db.execute(select(User).limit(1))).scalars().first()
        user_id = user.id if user else "nobody"

    # Act
    await section_generation.run_generation("campaign", "PEAKS", user_id)

    # Assert
    async with TestSessionLocal() as db:
        adv = await db.get(AdventureTemplate, "campaign")
    peaks = next(s for s in adv.world_sections if s["id"] == "PEAKS")
    assert peaks["status"] == "stub" and "no scenes" in peaks["generation_error"]


@pytest.mark.asyncio
async def test_plan_endpoint_returns_a_proposal(auth_client, setup_test_db, monkeypatch):
    plan = SimpleNamespace(
        sections=[SimpleNamespace(model_dump=lambda: {**PEAKS, "id": "MINES", "label": "Mines"})],
    )

    class _PlanLLM:
        async def aexecute_complex_task(self, **_kwargs):
            return plan

    monkeypatch.setattr(section_generator, "_llm", lambda _user: (_PlanLLM(), "model"))
    async with TestSessionLocal() as db:
        await _seed_template(db)
        adv = await db.get(AdventureTemplate, "campaign")
        adv.owner_id = (
            (await db.execute(select(User).where(User.username == "test_user"))).scalar_one().id
        )
        await db.commit()

    # Act
    resp = await auth_client.post(
        "/api/adventures/campaign/editor/sections/plan", json={"count": 1}
    )

    # Assert
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [s["id"] for s in body["sections"]] == ["HARBOR", "PEAKS", "MINES"]
    assert body["sections"][2]["status"] == "stub"
    assert "outline" not in body


# --- session expansion -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_expansion_adds_a_region_built_after_the_session_started(setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange: a session that knows only HARBOR; the template now also has PEAKS.
        adv = await _seed_template(db)
        snapshot = build_session_snapshot(adv)
        db.add(
            WorldScene(
                id="SQUARE", session_id="s1", label="Square", description="d", section_id="HARBOR"
            )
        )
        db.add(SessionState(session_id="s1", template_id="campaign", current_scene_id="SQUARE",
                            entity_states={"__manifest_snapshot__": snapshot, "KEY": {"x": 1}},
                            quests=[]))  # fmt: skip
        adv.world_sections = normalize_sections([HARBOR, {**PEAKS, "status": "built"}])
        adv.quests = [{"id": "Q_HERMIT", "title": "The Hermit"}]
        db.add(
            WorldScene(
                id="PASS", template_id="campaign", label="Pass", description="d", section_id="PEAKS"
            )
        )
        db.add(
            WorldExit(
                template_id="campaign",
                from_scene_id="SQUARE",
                to_scene_id="PASS",
                label="the high road",
                exit_type="bidirectional",
                travel_minutes=480,
            )
        )
        db.add(WorldEntity(id="HERMIT", template_id="campaign", entity_type="NPC", name="Hermit",
                           description="Old.", current_scene_id="PASS"))  # fmt: skip
        await db.commit()
        query = select(SessionState).where(SessionState.session_id == "s1")
        state = (await db.execute(query)).scalar_one()

        # Act
        before = [s["id"] for s in await pending_sections(db, state)]
        added = await expand_session(db, state)
        after = await pending_sections(db, state)

        # Assert
        rows = {
            r.id
            for r in (
                await db.execute(select(WorldScene).where(WorldScene.session_id == "s1"))
            ).scalars()
        }
        exits = (
            (await db.execute(select(WorldExit).where(WorldExit.session_id == "s1")))
            .scalars()
            .all()
        )
        hermit = (
            (await db.execute(select(WorldEntity).where(WorldEntity.session_id == "s1")))
            .scalars()
            .all()
        )
    assert before == ["PEAKS"] and [s["id"] for s in added] == ["PEAKS"] and after == []
    assert rows == {"SQUARE", "PASS"}
    assert [e.travel_minutes for e in exits] == [480]
    assert [h.id for h in hermit] == ["HERMIT"]
    assert state.entity_states["KEY"] == {"x": 1}
    assert [q["id"] for q in state.quests] == ["Q_HERMIT"]
    snap_sections = state.entity_states["__manifest_snapshot__"]["adventure"]["world_sections"]
    assert [s["id"] for s in snap_sections] == ["HARBOR", "PEAKS"]


# --- after the last chapter / after a generation ---------------------------------------------


@pytest.mark.asyncio
async def test_planned_regions_keep_the_campaign_going(setup_test_db):
    from backend.api.routes.adventures.campaign_continuation import (
        TO_BE_CONTINUED_NOTE,
        campaign_continues,
        take_to_be_continued_note,
    )

    async with TestSessionLocal() as db:
        # Arrange
        adv = await _seed_template(db)
        known = {"__manifest_snapshot__": {"adventure": {"world_sections": [HARBOR]}}}
        state = SessionState(template_id="campaign", session_id="none", entity_states=known)

        # Act
        planned = await campaign_continues(db, state)
        adv.world_sections = normalize_sections([HARBOR])
        await db.commit()
        finished = await campaign_continues(db, state)

    first, second = take_to_be_continued_note(state), take_to_be_continued_note(state)

    # Assert
    assert planned is True and finished is False
    assert first == TO_BE_CONTINUED_NOTE and second is None


@pytest.mark.asyncio
async def test_generation_notes_list_fixups_and_new_findings(setup_test_db, monkeypatch):
    finding = SimpleNamespace(severity="warn", message="Region 'Peaks' has no fast travel point.")
    rounds = iter([{}, {"new": finding}])

    async def _generated(*_args, **_kwargs):
        return ["Dropped on_init scripts."]

    async def _findings(*_args, **_kwargs):
        return next(rounds)

    monkeypatch.setattr(section_generation, "generate_section", _generated)
    monkeypatch.setattr(section_generation, "_findings", _findings)
    monkeypatch.setattr(section_generation, "session_factory", lambda: TestSessionLocal)
    async with TestSessionLocal() as db:
        await _seed_template(db)

    # Act
    await section_generation.run_generation("campaign", "PEAKS", "nobody")

    # Assert
    async with TestSessionLocal() as db:
        adv = await db.get(AdventureTemplate, "campaign")
    peaks = next(s for s in adv.world_sections if s["id"] == "PEAKS")
    assert peaks["generation_notes"] == [
        "Dropped on_init scripts.",
        "warn: Region 'Peaks' has no fast travel point.",
    ]


def test_quest_regions_reach_the_manifest_the_generation_and_the_agent():
    from backend.api.routes.adventures.agent_objectives import format_objectives
    from backend.engine.blueprint import analyze_blueprint
    from backend.engine.blueprint.merge import apply_blueprint

    # Arrange
    manifest = {"quests": []}
    region = _region()
    state = SimpleNamespace(
        quests=[{"id": "Q", "title": "The Hermit", "status": "open", "section_id": "PEAKS"}],
        active_sequence_id=None,
        entity_states={},
    )
    adventure = SimpleNamespace(world_sections=[HARBOR, {**PEAKS, "status": "built"}], sequences=[])

    # Act
    blueprint, _ = analyze_blueprint("[Sidequest: Q] The Hermit\nregion: PEAKS\n")
    apply_blueprint(manifest, blueprint)
    prepare_section(region, "PEAKS", _ledger())
    objectives = format_objectives(adventure, state)

    # Assert
    assert manifest["quests"][0]["section_id"] == "PEAKS"
    assert region["quests"][0]["section_id"] == "PEAKS"
    assert "The Hermit (continues in Peaks)" in objectives
