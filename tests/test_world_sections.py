"""World sections (regions): model, authoring paths, editor endpoints, sessions and the map.

Spec: docs/specs/world_sections.md (phase 1).
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from backend.api.routes.adventures.session_adventure import build_session_snapshot
from backend.core.world_validator import validate_adventure
from backend.engine.adventures.adventure_exporter import AdventureExporter
from backend.engine.blueprint import analyze_blueprint
from backend.engine.blueprint.merge import apply_blueprint
from backend.engine.interaction.location_context import build_location_context
from backend.engine.interaction.map_sections import attach_sections
from backend.engine.world.scene_fields import scene_content_from_dict
from backend.engine.world.sections import (
    normalize_sections,
    player_sections,
    region_line,
    section_id_or_none,
    session_manifest,
)
from backend.engine.world.world_manifest_applier import apply_manifest
from backend.engine.world.world_schemas import WorldManifesto, WorldSceneSchema
from backend.engine.world.world_section_schema import WorldSectionSchema
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.models.world_entity import WorldScene
from tests.conftest import TestSessionLocal

HARBOR = {"id": "HARBOR_TOWN", "label": "Harbor Town", "description": "A fishing port."}
PEAKS = {
    "id": "GLOOM_PEAKS",
    "label": "Gloom Peaks",
    "status": "stub",
    "brief": "Dwarven ruins.",
    "planned_links": [{"to_section_id": "HARBOR_TOWN", "travel_minutes": 480}],
}


# --- section model ---------------------------------------------------------------------------


def test_normalize_sections_cleans_ids_positions_and_links():
    # Arrange
    raw = [
        {"id": "harbor town", "label": "Harbor", "map_x": 140, "map_y": -3},
        {"id": "HARBOR_TOWN", "label": "Duplicate"},
        {**PEAKS, "planned_links": [*PEAKS["planned_links"], {"to_section_id": "NOWHERE"}]},
        {"label": "no id"},
    ]

    # Act
    sections = normalize_sections(raw)

    # Assert
    assert [s["id"] for s in sections] == ["HARBOR_TOWN", "GLOOM_PEAKS"]
    assert (sections[0]["map_x"], sections[0]["map_y"]) == (100.0, 0.0)
    assert sections[0]["status"] == "built"
    assert sections[1]["planned_links"] == [
        {"to_section_id": "HARBOR_TOWN", "travel_minutes": 480, "note": ""}
    ]
    assert section_id_or_none("  ") is None


def test_player_sections_hide_stubs_and_author_fields():
    # Act
    sections = player_sections([HARBOR, PEAKS])

    # Assert
    assert [s["id"] for s in sections] == ["HARBOR_TOWN"]
    assert not {"status", "brief", "summary", "planned_links"} & set(sections[0])


def test_session_manifest_drops_stub_sections():
    # Arrange
    manifest = {"sections": [HARBOR, PEAKS], "adventure": {"sections": [PEAKS]}}

    # Act
    copy = session_manifest(manifest)

    # Assert
    assert [s["id"] for s in copy["sections"]] == ["HARBOR_TOWN"]
    assert copy["adventure"]["sections"] == []
    assert len(manifest["sections"]) == 2  # the template manifest is untouched


def test_region_line_names_built_sections_only():
    # Act / Assert
    assert region_line([HARBOR], "HARBOR_TOWN") == "Region: Harbor Town: A fishing port."
    assert region_line([HARBOR, PEAKS], "GLOOM_PEAKS") == ""
    assert region_line([HARBOR], None) == ""


# --- authoring paths -------------------------------------------------------------------------


def test_blueprint_section_tags_and_scene_key_reach_the_manifest():
    # Arrange
    text = (
        "[Section: HARBOR_TOWN] Harbor Town\nPosition: 20, 65\nA fishing port.\n\n"
        "[Region: GLOOM_PEAKS] Gloom Peaks\nStatus: planned\nBrief: Dwarven ruins.\n"
        "Links: HARBOR_TOWN 8h\n\n"
        "[Scene: SQUARE] Square\nSection: HARBOR_TOWN\nThe market.\n"
    )
    manifest = {"scenes": [{"id": "SQUARE", "name": "Square", "description": "x"}]}

    # Act
    blueprint, missing = analyze_blueprint(text)
    violations = apply_blueprint(manifest, blueprint)

    # Assert
    assert blueprint.issues == [] and missing == [] and violations == []
    harbor, peaks = manifest["sections"]
    assert (harbor["map_x"], harbor["map_y"], harbor["description"]) == (
        20.0,
        65.0,
        "A fishing port.",
    )
    assert peaks["status"] == "stub"
    assert peaks["planned_links"] == [{"to_section_id": "HARBOR_TOWN", "travel_minutes": 480}]
    assert manifest["scenes"][0]["section_id"] == "HARBOR_TOWN"


def test_blueprint_rejects_a_bad_position():
    # Act
    blueprint, _ = analyze_blueprint("[Section: A] A\nPosition: 20\n")

    # Assert
    assert any("two numbers" in issue.message for issue in blueprint.issues)


def test_generation_schema_accepts_sections_and_scene_section():
    # Arrange
    scene_raw = {"id": "SQUARE", "name": "Square", "description": "d", "section_id": "HARBOR_TOWN"}

    # Act
    sections = [WorldSectionSchema.model_validate(s).model_dump() for s in (HARBOR, PEAKS)]
    scene = WorldSceneSchema.model_validate(scene_raw).model_dump()

    # Assert
    assert "sections" in WorldManifesto.model_fields
    assert [s["status"] for s in sections] == ["built", "stub"]
    assert normalize_sections(sections)[1]["planned_links"][0]["travel_minutes"] == 480
    assert scene_content_from_dict(scene)["section_id"] == "HARBOR_TOWN"


# --- validation ------------------------------------------------------------------------------


def _codes(payload: dict) -> set[str]:
    return {finding.code for finding in validate_adventure(payload)}


def test_validator_flags_missing_planned_and_unassigned_sections():
    # Arrange
    payload = {
        "adventure": {"world_sections": [HARBOR, PEAKS, {"id": "EMPTY", "label": "Empty"}]},
        "scenes": [
            {"id": "A", "section_id": "HARBOR_TOWN"},
            {"id": "B", "section_id": "GLOOM_PEAKS"},
            {"id": "C", "section_id": "GONE"},
            {"id": "D"},
        ],
    }

    # Act
    codes = _codes(payload)

    # Assert
    assert {
        "scene_in_planned_section",
        "scene_section_missing",
        "section_without_scenes",
        "scene_without_section",
    } <= codes


def test_validator_is_silent_without_sections():
    # Act
    codes = _codes({"adventure": {}, "scenes": [{"id": "A"}]})

    # Assert
    assert not {c for c in codes if "section" in c}


# --- runtime: prompt, snapshot and map -------------------------------------------------------


def test_location_context_carries_the_region_line():
    # Arrange
    scene = SimpleNamespace(id="SQUARE", label="Square", description="d", decorative_objects=[])

    # Act
    full = build_location_context(scene, region="Region: Harbor Town: A fishing port.")
    plain = build_location_context(scene)

    # Assert
    assert "Region: Harbor Town: A fishing port.\n" in full
    assert "Region:" not in plain


def test_session_snapshot_never_contains_stubs():
    # Arrange
    adventure = AdventureTemplate(
        id="adv",
        title="Campaign",
        world_sections=normalize_sections([HARBOR, PEAKS]),
        original_manifest={"sections": normalize_sections([HARBOR, PEAKS])},
    )

    # Act
    snapshot = build_session_snapshot(adventure)

    # Assert
    assert [s["id"] for s in snapshot["adventure"]["world_sections"]] == ["HARBOR_TOWN"]
    assert [s["id"] for s in snapshot["original_manifest"]["sections"]] == ["HARBOR_TOWN"]
    assert "brief" not in str(snapshot["adventure"]["world_sections"])


def test_map_shows_discovered_regions_and_links_but_not_unexplored_ones():
    # Arrange
    sections = [HARBOR, {"id": "WOODS", "label": "Woods"}, {"id": "CAVES", "label": "Caves"}]
    map_dict = {
        "nodes": {
            "SQUARE": {"id": "SQUARE"},
            "TRAIL": {"id": "TRAIL"},
            "GATE": {"id": "GATE", "is_revealed": True},
            "HOLE": {"id": "HOLE", "is_unknown": True},
        },
        "edges": [
            {"from": "SQUARE", "to": "TRAIL", "is_locked": False},
            {"from": "TRAIL", "to": "GATE", "is_locked": True},
            {"from": "TRAIL", "to": "HOLE", "is_locked": False},
        ],
        "current_scene_id": "SQUARE",
    }
    scene_sections = {"SQUARE": "HARBOR_TOWN", "TRAIL": "WOODS", "GATE": "WOODS", "HOLE": "CAVES"}

    # Act
    result = attach_sections(map_dict, scene_sections, sections)

    # Assert
    assert [(s["id"], s["discovery"]) for s in result["sections"]] == [
        ("HARBOR_TOWN", "visited"),
        ("WOODS", "visited"),
    ]
    assert result["section_links"] == [{"from": "HARBOR_TOWN", "to": "WOODS", "is_locked": False}]
    assert result["nodes"]["HOLE"]["section_id"] is None
    assert result["current_section_id"] == "HARBOR_TOWN"


def test_map_without_sections_stays_unchanged():
    # Act
    result = attach_sections({"nodes": {"A": {"id": "A"}}, "edges": []}, {"A": None}, None)

    # Assert
    assert result["sections"] == [] and result["section_links"] == []
    assert result["current_section_id"] is None


# --- editor endpoints ------------------------------------------------------------------------


async def _seed_template(sections=None) -> str:
    async with TestSessionLocal() as db:
        user = (
            (await db.execute(select(User).where(User.username == "test_user"))).scalars().first()
        )
        adv = AdventureTemplate(
            title="Regions",
            owner_id=user.id,
            world_sections=normalize_sections(sections) if sections else None,
            original_manifest={
                "scenes": [{"id": "SQUARE"}, {"id": "TRAIL"}],
                "sections": normalize_sections(sections or []),
            },
        )
        db.add(adv)
        await db.flush()
        for scene_id in ("SQUARE", "TRAIL"):
            db.add(WorldScene(id=scene_id, template_id=adv.id, label=scene_id, description="d"))
        await db.commit()
        return adv.id


async def _scene_sections(template_id: str) -> dict:
    async with TestSessionLocal() as db:
        rows = (
            await db.execute(select(WorldScene).where(WorldScene.template_id == template_id))
        ).scalars()
        return {row.id: row.section_id for row in rows}


@pytest.mark.asyncio
async def test_assigning_scenes_makes_a_planned_section_built(auth_client, setup_test_db):
    # Arrange
    template_id = await _seed_template([HARBOR, PEAKS])

    # Act
    resp = await auth_client.post(
        f"/api/adventures/{template_id}/editor/sections/assign",
        json={"section_id": "gloom peaks", "scene_ids": ["trail"]},
    )

    # Assert
    assert resp.status_code == 200, resp.text
    assert await _scene_sections(template_id) == {"SQUARE": None, "TRAIL": "GLOOM_PEAKS"}
    statuses = {s["id"]: s["status"] for s in resp.json()["sections"]}
    assert statuses["GLOOM_PEAKS"] == "built"
    async with TestSessionLocal() as db:
        adv = await db.get(AdventureTemplate, template_id)
        manifest_scene = adv.original_manifest["scenes"][1]
    assert manifest_scene == {"id": "TRAIL", "section_id": "GLOOM_PEAKS"}


@pytest.mark.asyncio
async def test_deleting_a_section_frees_its_scenes(auth_client, setup_test_db):
    # Arrange
    template_id = await _seed_template([HARBOR])
    await auth_client.post(
        f"/api/adventures/{template_id}/editor/sections/assign",
        json={"section_id": "HARBOR_TOWN", "scene_ids": ["SQUARE", "TRAIL"]},
    )

    # Act
    resp = await auth_client.put(
        f"/api/adventures/{template_id}/editor/sections", json={"sections": [PEAKS]}
    )

    # Assert
    assert resp.status_code == 200, resp.text
    assert resp.json()["cleared_scene_ids"] == ["SQUARE", "TRAIL"]
    assert await _scene_sections(template_id) == {"SQUARE": None, "TRAIL": None}
    async with TestSessionLocal() as db:
        adv = await db.get(AdventureTemplate, template_id)
    assert [s["id"] for s in adv.world_sections] == ["GLOOM_PEAKS"]
    assert [s["id"] for s in adv.original_manifest["sections"]] == ["GLOOM_PEAKS"]


@pytest.mark.asyncio
async def test_a_section_with_scenes_cannot_become_planned(auth_client, setup_test_db):
    # Arrange
    template_id = await _seed_template([HARBOR])
    await auth_client.post(
        f"/api/adventures/{template_id}/editor/sections/assign",
        json={"section_id": "HARBOR_TOWN", "scene_ids": ["SQUARE"]},
    )

    # Act
    resp = await auth_client.put(
        f"/api/adventures/{template_id}/editor/sections",
        json={"sections": [{**HARBOR, "status": "stub"}]},
    )

    # Assert
    assert resp.status_code == 400
    assert "cannot be marked as planned" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_scene_update_sets_and_clears_the_section(auth_client, setup_test_db):
    # Arrange
    template_id = await _seed_template([HARBOR])
    url = f"/api/adventures/{template_id}/editor/entity"

    # Act
    set_resp = await auth_client.patch(
        url, json={"target_type": "scene", "target_id": "SQUARE", "section_id": "HARBOR_TOWN"}
    )
    after_set = await _scene_sections(template_id)
    bad_resp = await auth_client.patch(
        url, json={"target_type": "scene", "target_id": "SQUARE", "section_id": "NOPE"}
    )
    clear_resp = await auth_client.patch(
        url, json={"target_type": "scene", "target_id": "SQUARE", "section_id": ""}
    )

    # Assert
    assert set_resp.status_code == 200, set_resp.text
    assert after_set["SQUARE"] == "HARBOR_TOWN"
    assert bad_resp.status_code == 404
    assert clear_resp.status_code == 200
    assert (await _scene_sections(template_id))["SQUARE"] is None


# --- export / import round trip --------------------------------------------------------------


@pytest.mark.asyncio
async def test_sections_survive_export_and_import(auth_client, setup_test_db, monkeypatch):
    monkeypatch.setattr(
        "backend.engine.media.media_engine.MediaEngine.generate_placeholder",
        AsyncMock(return_value="/data/placeholder.svg"),
    )
    # Arrange
    template_id = await _seed_template([HARBOR, PEAKS])
    await auth_client.post(
        f"/api/adventures/{template_id}/editor/sections/assign",
        json={"section_id": "HARBOR_TOWN", "scene_ids": ["SQUARE"]},
    )
    async with TestSessionLocal() as db:
        user = (await db.execute(select(User).limit(1))).scalars().first()
        db.add(AdventureTemplate(id="copy", title="Copy", owner_id=user.id))
        await db.commit()
        manifest = await AdventureExporter.build_full_manifest(db, template_id)

        # Act
        await apply_manifest(db, "copy", manifest)

    # Assert
    assert [s["id"] for s in manifest["sections"]] == ["HARBOR_TOWN", "GLOOM_PEAKS"]
    async with TestSessionLocal() as db:
        copy = await db.get(AdventureTemplate, "copy")
        sections = {s["id"]: s for s in copy.world_sections}
        exported_again = await AdventureExporter.build_full_manifest(db, "copy")
    assert sections["GLOOM_PEAKS"]["status"] == "stub"
    assert sections["GLOOM_PEAKS"]["brief"] == "Dwarven ruins."
    assert await _scene_sections("copy") == {"SQUARE": "HARBOR_TOWN", "TRAIL": None}
    assert exported_again["sections"] == manifest["sections"]


# --- world map image -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_drawing_needs_regions(auth_client, setup_test_db):
    # Arrange
    template_id = await _seed_template()

    # Act
    resp = await auth_client.post(f"/api/adventures/{template_id}/editor/sections/map-image")

    # Assert
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_map_prompt_can_be_edited_and_tone_and_style_are_optional(
    auth_client, setup_test_db, monkeypatch
):
    calls = []

    async def _draw(prompt, _template_id, _config, _keys, style_instruction=None):
        calls.append((prompt, style_instruction))
        return "/data/adventures/library/x/scenes/map.png"

    monkeypatch.setattr("backend.engine.media.media_engine.MediaEngine.generate_scene_image", _draw)
    # Arrange
    template_id = await _seed_template([HARBOR])
    async with TestSessionLocal() as db:
        adv = await db.get(AdventureTemplate, template_id)
        adv.selected_tone = {"id": "grim", "instruction": "Grim and rainy."}
        adv.selected_image_styles = [{"id": "ink", "instruction": "Ink drawing."}]
        await db.commit()
    url = f"/api/adventures/{template_id}/editor/sections/map-image"

    # Act
    info = (await auth_client.get(f"{url}/prompt")).json()
    await auth_client.post(
        url, json={"prompt": "A parchment map.", "use_style": True, "use_tone": True}
    )
    await auth_client.post(
        url, json={"prompt": "A parchment map.", "use_style": False, "use_tone": False}
    )

    # Assert
    assert "Harbor Town" in info["prompt"] and info["tone"] == "Grim and rainy."
    assert calls[0] == ("A parchment map. Mood and atmosphere: Grim and rainy.", "Ink drawing.")
    assert calls[1] == ("A parchment map.", None)


def test_tiles_grow_the_grid_only_next_to_the_map_and_shrink_again():
    from backend.engine.world.world_map_layout import place_tile, remove_tile

    # Act
    one = place_tile(None, 0, 0, "/a.png")
    wide = place_tile(one, 1, 0, "/b.png")
    tall = place_tile(wide, 0, 1, "/c.png")
    shrunk = remove_tile(remove_tile(tall, 0, 1), 1, 0)

    # Assert
    assert (wide["cols"], wide["rows"]) == (2, 1)
    assert (tall["cols"], tall["rows"]) == (2, 2) and len(tall["tiles"]) == 3
    assert (shrunk["cols"], shrunk["rows"]) == (1, 1)
    with pytest.raises(ValueError):
        place_tile(one, 2, 0, "/far.png")


def test_region_positions_follow_a_growing_grid():
    from backend.engine.world.world_map_layout import rescale_sections

    # Act
    sections = rescale_sections(
        normalize_sections([{**HARBOR, "map_x": 50, "map_y": 80}]), (1, 1), (2, 2)
    )

    # Assert
    assert (sections[0]["map_x"], sections[0]["map_y"]) == (25.0, 40.0)


def test_tile_prompt_names_its_part_and_its_regions():
    from backend.engine.world.world_map_layout import tile_prompt

    # Arrange: a 2x1 map; HARBOR lies in the right tile, PEAKS in the left one.
    adventure = SimpleNamespace(
        world_sections=[
            {**HARBOR, "map_x": 80, "map_y": 90},
            {"id": "PEAKS", "label": "Peaks", "map_x": 10, "map_y": 10, "status": "stub", "brief": "Ice."},
        ],
        plot="A storm.",
    )  # fmt: skip
    layout = {"cols": 2, "rows": 1, "tiles": [{"col": 0, "row": 0, "url": "/a.png"}]}

    # Act
    right = tile_prompt(adventure, layout, 1, 0)

    # Assert
    assert "column 2 of 2, row 1 of 1" in right
    assert "Harbor Town in the south: A fishing port." in right
    assert "Peaks" not in right and "No text" in right


@pytest.mark.asyncio
async def test_drawing_tiles_extends_the_map_and_moves_the_regions(
    auth_client, setup_test_db, monkeypatch
):
    monkeypatch.setattr(
        "backend.engine.media.media_engine.MediaEngine.generate_scene_image",
        AsyncMock(return_value="/data/adventures/library/x/scenes/tile.png"),
    )
    # Arrange
    template_id = await _seed_template([{**HARBOR, "map_x": 60, "map_y": 40}])
    url = f"/api/adventures/{template_id}/editor/sections/map-image"

    # Act
    first = await auth_client.post(url, json={"col": 0, "row": 0})
    second = await auth_client.post(url, json={"col": 1, "row": 0})
    world_map = (await auth_client.get(f"/api/adventures/{template_id}/map")).json()
    async with TestSessionLocal() as db:
        moved = (await db.get(AdventureTemplate, template_id)).world_sections[0]["map_x"]
    far = await auth_client.post(url, json={"col": 3, "row": 0})
    removed = await auth_client.delete(f"{url}?col=1&row=0")

    # Assert
    assert first.status_code == 200, first.text
    assert second.json()["world_map_layout"]["cols"] == 2
    assert world_map["world_map_layout"]["cols"] == 2
    assert moved == 30.0
    assert far.status_code == 400
    assert removed.json()["world_map_layout"]["cols"] == 1
    async with TestSessionLocal() as db:
        adv = await db.get(AdventureTemplate, template_id)
    assert adv.world_sections[0]["map_x"] == 60.0


@pytest.mark.asyncio
async def test_an_own_tile_can_be_uploaded(auth_client, setup_test_db, tmp_path, monkeypatch):
    import io

    from PIL import Image

    from backend.core.config import settings

    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    # Arrange
    template_id = await _seed_template([HARBOR])
    buffer = io.BytesIO()
    Image.new("RGB", (64, 36), "white").save(buffer, format="PNG")

    # Act
    resp = await auth_client.post(
        f"/api/adventures/{template_id}/editor/sections/map-image/upload",
        data={"col": "0", "row": "1"},
        files={"file": ("map.png", buffer.getvalue(), "image/png")},
    )

    # Assert
    assert resp.status_code == 200, resp.text
    layout = resp.json()["world_map_layout"]
    assert (layout["cols"], layout["rows"]) == (1, 2)
    assert "/visuals/world_map/" in layout["tiles"][0]["url"]


def test_imported_layout_keeps_only_tiles_with_files():
    from backend.engine.world.world_map_layout import imported_map_layout

    # Act
    layout = imported_map_layout(
        {"cols": 2, "rows": 1, "tiles": [{"col": 0, "row": 0, "url": "assets/a.png"},
                                         {"col": 1, "row": 0, "url": "assets/missing.png"}]},
        {"assets/a.png": "/data/adventures/library/new/a.png"},
    )  # fmt: skip

    # Assert
    assert layout["tiles"] == [{"col": 0, "row": 0, "url": "/data/adventures/library/new/a.png"}]
