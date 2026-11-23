"""Cut-scenes: library, session queue, tw.cutscene, chapter intros, the seen endpoint, transfer.

Engine: backend/engine/cutscenes/. Spec: docs/specs/cutscenes.md.
"""

import pytest

from backend.core.auth import create_access_token
from backend.engine.cutscenes.images import default_slide_prompt, style_instruction
from backend.engine.cutscenes.library import normalize_cutscenes
from backend.engine.cutscenes.queue import (
    CUTSCENE_STATE_KEY,
    apply_cutscene_ops,
    client_cutscene,
    mark_seen,
    queue_chapter_cutscene,
    queue_cutscene,
)
from backend.engine.cutscenes.transfer import (
    cloned_cutscenes,
    imported_cutscenes,
    localized_cutscenes,
    merged_cutscenes,
)
from backend.engine.scripting.context import GameContext
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldScene
from tests.conftest import TestSessionLocal

LIBRARY = [
    {
        "id": "intro",
        "title": "The Debt",
        "audio_track_id": "DREAD",
        "image_style": "comic",
        "slides": [
            {"text": "The village burns.", "image_url": "/data/adventures/library/T/a.png"},
            {"text": "  A wolf   howls.  ", "image_prompt": "a shadow wolf"},
            {"text": ""},
        ],
    },
    {"id": "INTRO", "title": "Duplicate", "slides": [{"text": "ignored"}]},
    {"id": "EMPTY", "slides": []},
]
TRACKS = [{"id": "DREAD", "name": "Dread", "url": "/data/adventures/library/T/audio/d.mp3"}]


# --- library -----------------------------------------------------------------------------------


def test_library_normalizes_ids_slides_and_style():
    # Act
    cutscenes = normalize_cutscenes(LIBRARY)

    # Assert
    intro = cutscenes[0]
    assert [c["id"] for c in cutscenes] == ["INTRO", "EMPTY"]
    assert intro["image_style"] == "comic"
    assert [s["text"] for s in intro["slides"]] == ["The village burns.", "A wolf howls."]
    assert intro["slides"][1]["image_url"] is None
    assert len({s["id"] for s in intro["slides"]}) == 2


def test_foreign_image_urls_are_dropped():
    # Act
    slide = normalize_cutscenes(
        [{"id": "X", "slides": [{"text": "t", "image_url": "https://evil.example/a.png"}]}]
    )[0]["slides"][0]

    # Assert
    assert slide["image_url"] is None


def test_cutscene_style_overrides_the_adventure_style():
    # Arrange
    adventure_styles = [{"id": "oil", "instruction": "oil painting"}]

    # Act
    own = style_instruction("loose watercolor", adventure_styles, [])
    inherited = style_instruction("", adventure_styles, [])

    # Assert
    assert own == "loose watercolor"
    assert inherited == "oil painting"
    assert "no text" in default_slide_prompt("Crimson Debt", "Intro", "The village burns.")


# --- queue and script ------------------------------------------------------------------------


def test_script_play_is_queued_once_and_resolved_for_the_client():
    # Arrange
    context = GameContext()
    context.cutscene.play("intro")
    context.cutscenes.play("INTRO")
    states: dict = {}

    # Act
    apply_cutscene_ops(states, context.changeset.cutscene_ops)
    shown = client_cutscene(states, LIBRARY, TRACKS, "T")

    # Assert
    assert len(states[CUTSCENE_STATE_KEY]["queue"]) == 1
    assert shown["id"] == "INTRO"
    assert shown["audio"] == {"id": "DREAD", "url": TRACKS[0]["url"]}
    assert [s["text"] for s in shown["slides"]] == ["The village burns.", "A wolf howls."]


def test_chapter_intro_plays_first_and_seen_removes_it():
    # Arrange
    states: dict = {}
    queue_cutscene(states, "EMPTY")
    queue_cutscene(states, "OTHER")

    # Act
    queued = queue_chapter_cutscene(states, {"id": "SEQ_1", "start_cutscene_id": "intro"}, True)
    first = states[CUTSCENE_STATE_KEY]["queue"][0]
    removed = mark_seen(states, first["token"])

    # Assert
    assert queued and first["id"] == "INTRO"
    assert removed
    assert [e["id"] for e in states[CUTSCENE_STATE_KEY]["queue"]] == ["EMPTY", "OTHER"]
    assert client_cutscene(states, LIBRARY, TRACKS, "T") is None  # empty / unknown ones skip


# --- transfer --------------------------------------------------------------------------------


def test_export_import_and_clone_keep_slide_images():
    # Arrange
    url = "/data/adventures/library/OLD/visuals/cutscene/a.png"
    library = [{"id": "INTRO", "slides": [{"text": "t", "image_url": url}]}]

    # Act
    exported = localized_cutscenes(library, lambda u: "assets/a.png")
    imported = imported_cutscenes(exported, {"assets/a.png": "/data/adventures/library/NEW/a.png"})
    cloned = cloned_cutscenes(library, lambda u: u.replace("OLD", "NEW"))

    # Assert
    assert exported[0]["slides"][0]["image_url"] == "assets/a.png"
    assert imported[0]["slides"][0]["image_url"] == "/data/adventures/library/NEW/a.png"
    assert cloned[0]["slides"][0]["image_url"].startswith("/data/adventures/library/NEW/")


def test_reapplied_manifest_keeps_drawn_images():
    # Arrange
    stored = [{"id": "INTRO", "slides": [{"text": "old", "image_url": "/data/x/a.png"}]}]
    incoming = [{"id": "INTRO", "slides": [{"text": "new", "image_prompt": "p"}]}]

    # Act
    merged = merged_cutscenes(stored, incoming)

    # Assert
    assert merged[0]["slides"][0] == {**merged[0]["slides"][0], "text": "new"}
    assert merged[0]["slides"][0]["image_url"] == "/data/x/a.png"
    assert merged_cutscenes(stored, None)[0]["id"] == "INTRO"


# --- session start and endpoint --------------------------------------------------------------


def _headers(username: str) -> dict:
    return {"Authorization": f"Bearer {create_access_token(data={'sub': username})}"}


@pytest.mark.asyncio
async def test_first_chapter_intro_reaches_the_client_until_seen(client, setup_test_db):
    # Arrange
    async with TestSessionLocal() as db:
        user = User(username="cutter", hashed_password="x", role="admin")
        db.add(user)
        await db.flush()
        template = AdventureTemplate(
            title="Cut",
            owner_id=user.id,
            version="2.0.0",
            is_ready=True,
            creation_status="Ready",
            original_manifest={"version": "2.0.0", "start_scene_id": "HALL"},
            cutscenes=LIBRARY,
            audio_tracks=TRACKS,
            sequences=[{"id": "SEQ_1", "order": 1, "title": "One", "start_cutscene_id": "INTRO"}],
        )
        db.add(template)
        await db.flush()
        db.add(WorldScene(id="HALL", template_id=template.id, label="Hall", description="A hall."))
        db.add(Avatar(user_id=user.id, template_id=template.id, name="Hero", inventory=[]))
        await db.commit()
        template_id = template.id
    start = await client.post(
        f"/api/adventures/{template_id}/sessions/start", headers=_headers("cutter")
    )
    game_id = start.json()["game_id"]

    # Act
    shown = await client.get(f"/api/adventures/{game_id}/chat", headers=_headers("cutter"))
    cutscene = shown.json()["cutscene"]
    seen = await client.post(
        f"/api/adventures/{game_id}/cutscene/seen",
        json={"token": cutscene["token"]},
        headers=_headers("cutter"),
    )

    # Assert
    assert cutscene["id"] == "INTRO" and len(cutscene["slides"]) == 2
    assert seen.status_code == 200 and seen.json()["cutscene"] is None
    async with TestSessionLocal() as db:
        state = await db.get(SessionState, game_id)
        assert state is None or not (state.entity_states or {})[CUTSCENE_STATE_KEY]["queue"]


# --- validation ------------------------------------------------------------------------------


def test_validator_reports_unknown_cutscene_references():
    # Arrange
    from backend.core.world_validator import validate_adventure

    payload = {
        "adventure": {
            "title": "Cut",
            "cutscenes": [{"id": "INTRO", "audio_track_id": "NOPE", "slides": [{"text": "a"}]}],
            "sequences": [
                {"id": "SEQ_1", "order": 1, "title": "One", "start_cutscene_id": "OUTRO"}
            ],
            "init_script": "tw.cutscene.play('GHOST')\ntw.cutscene.play('INTRO')",
        },
        "protagonist": {},
        "scenes": [],
        "npcs": [],
        "objects": [],
        "exits": [],
        "entities_all": [],
    }

    # Act
    codes = {f.code for f in validate_adventure(payload)}

    # Assert
    assert {
        "chapter_cutscene_missing",
        "cutscene_audio_missing",
        "script_cutscene_missing",
    } <= codes


def test_every_autocompleted_cutscene_method_exists_on_the_proxy():
    # Arrange
    import re
    from pathlib import Path

    from backend.engine.cutscenes.proxy import CutsceneProxy

    source = (
        Path(__file__).resolve().parents[1] / "frontend/src/utils/twScriptApiDefinitions.ts"
    ).read_text(encoding="utf-8")
    block = source[source.index("  cutscene: {") : source.index("  time: {")]

    # Act
    methods = re.findall(r"name: '(\w+)', kind: 'method'", block)

    # Assert
    assert methods
    assert [m for m in methods if not callable(getattr(CutsceneProxy, m, None))] == []
