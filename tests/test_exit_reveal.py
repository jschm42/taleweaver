"""Revealed exits: the target scene is known on the map and the exit tile before a visit."""

from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from backend.engine.blueprint import analyze_blueprint
from backend.engine.interaction.map_engine import MapEngine
from backend.models.world_entity import WorldExit, WorldScene
from tests.conftest import TestSessionLocal


def _exit(to_scene: str, revealed: bool) -> SimpleNamespace:
    return SimpleNamespace(
        id=f"exit-{to_scene}",
        from_scene_id="HALL",
        to_scene_id=to_scene,
        label="an old rusty gate",
        exit_type="bidirectional",
        is_locked=False,
        is_revealed=revealed,
        lock_description=None,
        code_to_unlock=None,
        item_to_unlock=None,
        rule_to_unlock=None,
    )


def _visited_hall() -> dict:
    return {"nodes": {"HALL": {"id": "HALL", "label": "Hall"}}, "edges": []}


# --- Map ----------------------------------------------------------------------------------


def test_revealed_exit_makes_its_target_known() -> None:
    # Arrange
    exits = [_exit("COMBAT_LAB", revealed=True), _exit("CELLAR", revealed=False)]

    # Act
    result = MapEngine.augment_map_data(_visited_hall(), exits, "HALL")

    # Assert
    lab, cellar = result["nodes"]["COMBAT_LAB"], result["nodes"]["CELLAR"]
    assert (lab["is_unknown"], lab["is_revealed"], lab["label"]) == (False, True, "")
    assert cellar["is_unknown"] is True
    edge = next(e for e in result["edges"] if e["to"] == "COMBAT_LAB")
    assert edge["is_revealed"] is True


def test_revealed_target_does_not_count_as_visited() -> None:
    # Arrange: a second exit links the revealed scene to another unvisited one.
    exits = [
        _exit("COMBAT_LAB", revealed=True),
        SimpleNamespace(
            id="lab-cellar",
            from_scene_id="COMBAT_LAB",
            to_scene_id="HALL_2",
            label="a hatch",
            exit_type="one_way",
            is_locked=False,
            is_revealed=False,
        ),
    ]
    start = _visited_hall()
    start["nodes"]["HALL_2"] = {"id": "HALL_2", "label": "Second Hall"}

    # Act
    result = MapEngine.augment_map_data(start, exits, "HALL")

    # Assert: no edge between the revealed (unvisited) lab and the visited second hall.
    assert not any(e.get("id") == "lab-cellar" for e in result["edges"])


def test_visited_target_stays_visited_when_revealed() -> None:
    # Arrange
    start = _visited_hall()
    start["nodes"]["COMBAT_LAB"] = {"id": "COMBAT_LAB", "label": "Combat Lab"}

    # Act
    result = MapEngine.augment_map_data(start, [_exit("COMBAT_LAB", revealed=True)], "HALL")

    # Assert
    assert result["nodes"]["COMBAT_LAB"] == {"id": "COMBAT_LAB", "label": "Combat Lab"}


# --- Blueprint ----------------------------------------------------------------------------


def test_blueprint_exit_accepts_revealed() -> None:
    # Act
    blueprint, _ = analyze_blueprint(
        "[Scene: HALL] Hall\n"
        "[Scene: COMBAT_LAB] Combat Lab\n"
        "[Exit: HALL <-> COMBAT_LAB] a signposted door\n"
        "revealed: yes\n"
    )

    # Assert
    exit_block = blueprint.first("exit")
    assert not [issue for issue in blueprint.issues if issue.severity == "error"]
    assert exit_block.fields["is_revealed"].value is True


# --- Editor API -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_editor_creates_and_updates_revealed_exit(auth_client: AsyncClient) -> None:
    # Arrange
    created = await auth_client.post(
        "/api/adventures/", json={"title": "Reveal Quest", "avatar_name": "Hero"}
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
            "label": "a signposted door",
            "is_revealed": True,
        },
    )
    assert response.status_code == 200, response.text
    exit_id = response.json()["exit"]["id"]
    update = await auth_client.patch(
        f"/api/adventures/{adv_id}/editor/entity",
        json={"target_type": "exit", "target_id": exit_id, "revealed": False},
    )

    # Assert
    assert update.status_code == 200, update.text
    async with TestSessionLocal() as db:
        stored = await db.scalar(select(WorldExit.is_revealed).where(WorldExit.id == exit_id))
        assert stored is False


def test_revealed_exits_of_other_visited_scenes_are_shown() -> None:
    # Arrange: the player stands in the workshop; the hall (visited) has a revealed exit.
    start = _visited_hall()
    start["nodes"]["WORKSHOP"] = {"id": "WORKSHOP", "label": "Workshop"}
    exits = [_exit("COMBAT_LAB", revealed=True), _exit("CELLAR", revealed=False)]

    # Act
    result = MapEngine.augment_map_data(start, exits, "WORKSHOP")

    # Assert: the revealed lab shows up, the unrevealed cellar stays hidden.
    assert result["nodes"]["COMBAT_LAB"]["is_revealed"] is True
    assert "CELLAR" not in result["nodes"]
    assert any(e["to"] == "COMBAT_LAB" for e in result["edges"])
