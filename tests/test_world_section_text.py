"""AI text for a region's description and brief (Regions page, engine/world/section_text.py)."""

from types import SimpleNamespace

import pytest
from sqlalchemy import select

from backend.api.routes.adventures.editing import section_text_routes
from backend.engine.world.section_text import build_section_text_prompt, clean_section_text
from backend.engine.world.sections import normalize_sections
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.models.world_entity import WorldScene
from tests.conftest import TestSessionLocal

HARBOR = {"id": "HARBOR", "label": "Harbor", "description": "A port.", "status": "built",
          "summary": "Fishers and a dark lighthouse."}  # fmt: skip
PEAKS = {
    "id": "PEAKS",
    "label": "Peaks",
    "description": "",
    "status": "stub",
    "brief": "Dwarven ruins.",
    "planned_links": [{"to_section_id": "HARBOR", "travel_minutes": 480}],
}


def _adventure(**overrides):
    values = {
        "title": "Campaign",
        "teaser": "A storm is coming.",
        "plot": "The keeper must relight the lighthouse.",
        "sequences": [{"order": 2, "title": "The Peaks"}, {"order": 1, "title": "Harbor"}],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_prompt_holds_plot_region_routes_scenes_and_other_regions():
    # Arrange
    sections = normalize_sections([HARBOR, PEAKS])

    # Act
    prompt = build_section_text_prompt(
        _adventure(), sections[1], sections, [("Gate", "Frozen doors.")], "description"
    )

    # Assert
    assert "Plot: The keeper must relight the lighthouse." in prompt
    assert "Current brief: Dwarven ruins." in prompt
    assert "Route to: Harbor, 8.0 h travel" in prompt
    assert "- Gate: Frozen doors." in prompt
    assert "- Harbor [built]: Fishers and a dark lighthouse." in prompt
    assert prompt.index("1. Harbor") < prompt.index("2. The Peaks")
    assert "DESCRIPTION" in prompt and "At most 2000 characters" in prompt


def test_clean_text_strips_labels_fences_and_limits_the_brief():
    # Act
    fenced = clean_section_text("```\nbrief: Build a ruin.\n```", "brief")
    long_text = clean_section_text("x" * 5000, "brief")

    # Assert
    assert fenced == "Build a ruin."
    assert len(long_text) == 1500


class _FakeLLM:
    prompts: list[str] = []

    def __init__(self, **_kwargs):
        pass

    async def aexecute_simple_task(self, **kwargs):
        _FakeLLM.prompts.append(kwargs["user_prompt"])
        return '"Snow-choked halls of a fallen dwarven kingdom."'


@pytest.mark.asyncio
async def test_endpoint_writes_text_for_an_unsaved_region(auth_client, setup_test_db, monkeypatch):
    monkeypatch.setattr(section_text_routes, "GameMasterLLM", _FakeLLM)
    async with TestSessionLocal() as db:
        # Arrange: the template knows only HARBOR; PEAKS exists in the draft only.
        owner = (await db.execute(select(User).where(User.username == "test_user"))).scalar_one()
        db.add(AdventureTemplate(id="campaign", title="Campaign", owner_id=owner.id,
                                 plot="Relight the lighthouse.", world_sections=[HARBOR]))  # fmt: skip
        db.add(WorldScene(id="SQUARE", template_id="campaign", label="Square", description="d",
                          section_id="HARBOR"))  # fmt: skip
        await db.commit()

    # Act
    resp = await auth_client.post(
        "/api/adventures/campaign/editor/sections/generate-text",
        json={"field": "description", "section_id": "PEAKS", "sections": [HARBOR, PEAKS]},
    )
    missing = await auth_client.post(
        "/api/adventures/campaign/editor/sections/generate-text",
        json={"field": "brief", "section_id": "MINES", "sections": [HARBOR]},
    )

    # Assert
    assert resp.status_code == 200, resp.text
    assert resp.json()["generated_text"] == "Snow-choked halls of a fallen dwarven kingdom."
    assert "Relight the lighthouse." in _FakeLLM.prompts[-1]
    assert missing.status_code == 400
    async with TestSessionLocal() as db:
        adv = await db.get(AdventureTemplate, "campaign")
    assert [s["id"] for s in adv.world_sections] == ["HARBOR"]
