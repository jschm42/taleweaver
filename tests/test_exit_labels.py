"""Exit labels are required; legacy exits without one are named after their target scene."""

from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from backend.engine.blueprint.merge import _default_exit
from backend.engine.world.exit_labels import (
    exit_display_name,
    exit_phrase,
    exit_sentence_name,
    exit_target_scene_id,
    scene_title_from_id,
)
from backend.models.world_entity import WorldExit, WorldScene
from tests.conftest import TestSessionLocal

# --- Naming rules ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "target_name", "target_id", "expected"),
    [
        ("a heavy oak door", "Combat Lab", "COMBAT_LAB", "a heavy oak door"),
        ("", "Combat Lab", "COMBAT_LAB", "Combat Lab"),
        ("   ", None, "COMBAT_LAB", "Combat Lab"),
        (None, None, None, "Exit"),
    ],
)
def test_display_name_prefers_label_then_target(label, target_name, target_id, expected) -> None:
    # Act
    name = exit_display_name(label, target_name, target_id)

    # Assert
    assert name == expected


def test_phrase_names_the_way_to_the_target() -> None:
    # Act
    labelled = exit_phrase("a rope ladder", target_scene_id="ATTIC")
    unlabelled = exit_phrase("", target_scene_id="time-machine_lab")
    unknown = exit_phrase("")

    # Assert
    assert labelled == "a rope ladder"
    assert unlabelled == "the way to Time Machine Lab"
    assert unknown == "the exit"


def test_two_way_exit_is_named_after_the_scene_on_the_other_side() -> None:
    # Arrange
    world_exit = SimpleNamespace(label="", from_scene_id="HALL", to_scene_id="COMBAT_LAB")

    # Act
    from_hall = exit_sentence_name(world_exit, "HALL")
    from_lab = exit_sentence_name(world_exit, "COMBAT_LAB")

    # Assert
    assert exit_target_scene_id(world_exit, "COMBAT_LAB") == "HALL"
    assert from_hall == "The way to Combat Lab"
    assert from_lab == "The way to Hall"


def test_scene_title_from_id() -> None:
    # Act / Assert
    assert scene_title_from_id("NPC_LAB") == "Npc Lab"
    assert scene_title_from_id(None) == ""


def test_blueprint_exit_without_label_gets_a_generic_passage_label() -> None:
    # Act
    entry = _default_exit(SimpleNamespace())

    # Assert
    assert entry["label"] == "a passage"


# --- Editor API -------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_editor_rejects_an_exit_without_label(auth_client: AsyncClient) -> None:
    # Arrange
    created = await auth_client.post(
        "/api/adventures/", json={"title": "Exit Label Quest", "avatar_name": "Hero"}
    )
    assert created.status_code == 201, created.text
    adv_id = created.json()["adventure_id"]
    async with TestSessionLocal() as db:
        db.add_all(
            [
                WorldScene(id="LAB_HALL", template_id=adv_id, label="Hall", description="H"),
                WorldScene(id="COMBAT_LAB", template_id=adv_id, label="Combat", description="C"),
            ]
        )
        await db.commit()

    # Act
    response = await auth_client.post(
        f"/api/adventures/{adv_id}/editor/exit",
        json={
            "from_scene_id": "LAB_HALL",
            "to_scene_id": "COMBAT_LAB",
            "label": "   ",
            "exit_type": "bidirectional",
        },
    )

    # Assert
    assert response.status_code == 400, response.text
    async with TestSessionLocal() as db:
        count = len(
            (await db.execute(select(WorldExit.id).where(WorldExit.template_id == adv_id))).all()
        )
        assert count == 0
