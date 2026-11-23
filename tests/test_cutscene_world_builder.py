"""Cut-scenes through the World-Builder: blueprint block -> manifest, schema -> manifest apply."""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from backend.engine.blueprint import analyze_blueprint, apply_blueprint, prepare_blueprint
from backend.engine.blueprint.prompt import blueprint_payload
from backend.engine.world.world_cutscene_schema import CutsceneSchema
from backend.engine.world.world_manifest_applier import apply_manifest
from backend.engine.world.world_schemas import SequenceSchema
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from tests.conftest import TestSessionLocal

BLUEPRINT = """A blood debt.

[World]
intro_cutscene: INTRO

[Scene: VILLAGE] Ashford
A village ringed by black fire.

[Chapter] The Debt
cutscene: INTRO

[Cutscene: INTRO] The Crimson Debt
style: comic book
The village burns inside a ring of black fire.
+ Nobody remembers who lit it.
A shadow wolf watches from the hill.
image 1: a medieval village ringed by black fire at night
"""


def test_blueprint_cutscene_reaches_the_manifest_and_the_chapter():
    # Arrange
    prepared = prepare_blueprint(BLUEPRINT)
    assert prepared is not None
    manifest = {
        "scenes": [{"id": "VILLAGE", "name": "Ashford", "description": "Fire."}],
        "sequences": [{"order": 1, "id": "SEQ_1", "title": "The Debt"}],
        "cutscenes": [
            {
                "id": "INTRO",
                "slides": [
                    {"text": "LLM text", "image_prompt": "x"},
                    {"text": "b", "image_prompt": "wolf"},
                ],
            }
        ],
    }

    # Act
    payload = blueprint_payload(prepared.blueprint)
    apply_blueprint(manifest, prepared.blueprint)

    # Assert
    assert "cutscenes" in payload
    cutscene = manifest["cutscenes"][0]
    assert cutscene["title"] == "The Crimson Debt"
    assert cutscene["image_style"] == "comic book"
    assert [s["passages"] for s in cutscene["slides"]] == [
        ["The village burns inside a ring of black fire.", "Nobody remembers who lit it."],
        ["A shadow wolf watches from the hill."],
    ]
    assert cutscene["slides"][0]["image_prompt"].startswith("a medieval village")
    assert cutscene["slides"][1]["image_prompt"] == "wolf"  # LLM prompt kept where none given
    assert not any(key.startswith("image_") and key != "image_style" for key in cutscene)
    assert manifest["sequences"][0]["start_cutscene_id"] == "INTRO"
    assert manifest["intro_cutscene_id"] == "INTRO"


def test_cutscene_without_slides_warns():
    # Act
    blueprint, missing = analyze_blueprint("[Cutscene: EMPTY] Nothing\nimage 2: a door\n")

    # Assert
    messages = [w.message for w in blueprint.warnings]
    assert any("has no slide" in m for m in messages)
    assert any("image 2 has no slide" in m for m in messages)
    assert "EMPTY" not in missing


def test_generation_schema_accepts_cutscenes():
    # Act
    cutscene = CutsceneSchema.model_validate(
        {"id": "INTRO", "slides": [{"text": "a", "image_prompt": "b"}], "image_style": "watercolor"}
    )
    sequence = SequenceSchema.model_validate(
        {"id": "SEQ_1", "order": 1, "title": "One", "start_cutscene_id": "INTRO"}
    )

    # Assert
    assert cutscene.slides[0].text == "a"
    assert sequence.start_cutscene_id == "INTRO"


@pytest.mark.asyncio
async def test_manifest_apply_stores_cutscenes(auth_client, setup_test_db, monkeypatch):
    # Arrange
    monkeypatch.setattr(
        "backend.engine.media.media_engine.MediaEngine.generate_placeholder",
        AsyncMock(return_value="/data/placeholder.svg"),
    )
    async with TestSessionLocal() as db:
        user = (await db.execute(select(User).limit(1))).scalars().first()
        db.add(AdventureTemplate(id="cut-tpl", title="Cut", owner_id=user.id))
        await db.commit()
        manifest = {
            "scenes": [{"id": "START", "label": "Start", "description": "A room."}],
            "sequences": [
                {"id": "SEQ_1", "order": 1, "title": "One", "start_cutscene_id": "INTRO"}
            ],
            "cutscenes": [{"id": "intro", "title": "Intro", "slides": [{"text": "It begins."}]}],
            "intro_cutscene_id": "intro",
        }

        # Act
        await apply_manifest(db, "cut-tpl", manifest)

    # Assert
    async with TestSessionLocal() as db:
        adventure = await db.get(AdventureTemplate, "cut-tpl")
        assert adventure.cutscenes[0]["id"] == "INTRO"
        assert adventure.cutscenes[0]["slides"][0]["passages"] == ["It begins."]
        assert adventure.sequences[0]["start_cutscene_id"] == "INTRO"
        assert adventure.intro_cutscene_id == "INTRO"
