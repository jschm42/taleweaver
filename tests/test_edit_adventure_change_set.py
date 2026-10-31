"""Agent change sets: editor operations applied in one transaction, dry run by default."""

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.api.routes.adventures.editing.change_set import (
    ChangeSetError,
    DeferredCommitSession,
    apply_change_set,
)
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene
from tests.conftest import test_engine

Session = async_sessionmaker(bind=test_engine, class_=DeferredCommitSession, expire_on_commit=False)

PUZZLE = """
if 'MOON_GEM' in added_item_ids:
    tw.exits.unlock('HALL', 'CRYPT')
    tw.narrate('The altar swallows the gem.')
"""


async def _seed() -> None:
    async with Session() as db:
        owner = User(id="owner-1", username="author", hashed_password="pw", role="user")
        adv = AdventureTemplate(
            id="adv-1",
            title="Moon Temple",
            owner_id=owner.id,
            original_manifest={"scenes": [], "exits": [], "scripts": []},
        )
        hall = WorldScene(id="HALL", template_id=adv.id, label="Hall", description="A hall.")
        db.add_all([owner, adv, hall])
        await db.commit_for_real()


async def _row(db, model, row_id: str):
    return (await db.execute(select(model).where(model.id == row_id))).scalars().first()


def _crypt_ops() -> list[dict]:
    return [
        {"op": "create_scene", "scene_id": "CRYPT", "label": "Crypt", "description": "Dark."},
        {
            "op": "create_exit",
            "ref": "crypt_door",
            "from_scene_id": "HALL",
            "to_scene_id": "CRYPT",
            "label": "Stone door",
            "exit_type": "bidirectional",
        },
        {
            "op": "update",
            "target_type": "exit",
            "target_id": "$crypt_door",
            "locked": True,
            "description": "A moon-shaped hollow seals the door.",
        },
        {
            "op": "create_entity",
            "entity_id": "MOON_ALTAR",
            "entity_type": "OBJECT",
            "item_type": "CONTAINER",
            "is_portable": False,
            "scene_id": "HALL",
            "name": "Moon Altar",
            "description": "An altar with a round hollow.",
        },
        {
            "op": "update",
            "target_type": "object",
            "target_id": "MOON_ALTAR",
            "on_items_added_script": PUZZLE,
        },
        {"op": "append_init_script", "code": "def moon_hint():\n    return 'Silver opens stone.'"},
    ]


async def test_change_set_builds_a_scripted_scene_and_commits():
    # Arrange
    await _seed()

    # Act
    async with Session() as db:
        result = await apply_change_set(db, "adv-1", _crypt_ops(), base_dir=Path("."))
        await db.commit_for_real()

    # Assert
    async with Session() as db:
        crypt = await _row(db, WorldScene, "CRYPT")
        door = (await db.execute(select(WorldExit))).scalars().one()
        altar = await _row(db, WorldEntity, "MOON_ALTAR")
        adv = await db.get(AdventureTemplate, "adv-1")
    assert crypt.label == "Crypt"
    assert (door.id, door.is_locked) == (result.refs["crypt_door"], True)
    assert "tw.exits.unlock" in altar.metadata_json["on_items_added_script"]
    assert "def moon_hint" in adv.init_script
    assert adv.original_manifest["exits"][0]["id"] == door.id
    assert result.new_errors == []


async def test_route_reference_and_rollback_keep_db_untouched():
    # Arrange
    await _seed()
    ops = [
        *_crypt_ops()[:2],
        {"op": "update", "target_type": "exit", "target_id": "HALL->CRYPT", "name": "Old door"},
    ]

    # Act
    async with Session() as db:
        result = await apply_change_set(db, "adv-1", ops, base_dir=Path("."))
        await db.rollback()

    # Assert
    async with Session() as db:
        assert await _row(db, WorldScene, "CRYPT") is None
    assert result.applied[-1].startswith("update: exit ")


@pytest.mark.parametrize(
    ("operation", "message"),
    [
        (
            {"op": "create_scene", "scene_id": "X", "label": "X", "description": "X", "lable": 1},
            "lable",
        ),
        (
            {
                "op": "update",
                "target_type": "scene",
                "target_id": "HALL",
                "on_enter_scene_script": "if :",
            },
            "syntax",
        ),
        ({"op": "teleport"}, "unknown op"),
        ({"op": "set_init_script", "code": {"$file": "../outside.py"}}, "outside"),
        (
            {"op": "update", "target_type": "exit", "target_id": "$nope", "name": "x"},
            "Unknown reference",
        ),
    ],
)
async def test_invalid_operations_are_rejected(operation, message, tmp_path):
    # Arrange
    await _seed()

    # Act / Assert
    async with Session() as db:
        with pytest.raises(ChangeSetError, match=message):
            await apply_change_set(db, "adv-1", [operation], base_dir=tmp_path)
        await db.rollback()


async def test_file_values_are_read_from_the_change_set_folder(tmp_path):
    # Arrange
    await _seed()
    (tmp_path / "init.py").write_text("def helper():\n    return 1\n", encoding="utf-8")

    # Act
    async with Session() as db:
        await apply_change_set(
            db, "adv-1", [{"op": "set_init_script", "code": {"$file": "init.py"}}], tmp_path
        )
        init_script = (await db.get(AdventureTemplate, "adv-1")).init_script
        await db.rollback()

    # Assert
    assert init_script.startswith("def helper")
