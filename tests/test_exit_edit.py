"""Tests for the exit update path used by EditExitModal."""

import pytest
from httpx import ASGITransport, AsyncClient

from backend.core.auth import create_access_token
from backend.core.database import get_db
from backend.main import app
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene
from tests.conftest import TestSessionLocal


def _auth_headers(username: str) -> dict:
    token = create_access_token(data={"sub": username})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def client():
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def override_get_db():
    async with TestSessionLocal() as session:
        yield session


async def test_exit_edit_persists_code_and_item_lock(client, setup_test_db):
    """Editing an existing exit must persist the lock-field changes.

    Mirrors the frontend's EditExitModal flow: PATCH /editor/entity with
    the lock-field update must round-trip on the database.
    """
    user = User(username="exit_edit_user", hashed_password="x", role="admin")
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        adv_id = "tpl-exit-edit"
        tpl = AdventureTemplate(
            id=adv_id,
            owner_id=user.id,
            title="Exit Edit Test",
            version="1.0",
            rule_enforcement_mode="rpg",
            is_ready=True,
            creation_status="Ready",
            generate_scene_images=False,
            generate_npc_images=False,
            generate_item_images=False,
            teaser="t",
            rules="r",
            plot="p",
            intro_text="i",
            completed_condition="done",
            gameover_condition="lost",
            tts_director_notes="notes",
            quests=[],
        )
        db.add(tpl)
        db.add(WorldScene(id="SCENE_A", template_id=adv_id, label="A", description="A"))
        db.add(WorldScene(id="SCENE_B", template_id=adv_id, label="B", description="B"))
        db.add(
            WorldEntity(
                id="BRONZE_KEY",
                template_id=adv_id,
                entity_type="OBJECT",
                name="Bronze Key",
                description="Unlocks the door.",
                current_scene_id="SCENE_A",
                item_type="DEFAULT",
            )
        )
        seeded_exit = WorldExit(
            template_id=adv_id,
            from_scene_id="SCENE_A",
            to_scene_id="SCENE_B",
            label="A locked door",
            is_locked=True,
            code_to_unlock="1331",
            lock_description="Requires a code.",
            exit_type="one_way",
        )
        db.add(seeded_exit)
        await db.commit()
        exit_id = seeded_exit.id

    payload = {
        "target_type": "exit",
        "target_id": exit_id,
        "name": "A locked door (renamed)",
        "description": "Updated description.",
        "exit_type": "one_way",
        "locked": True,
        "code_to_unlock": "",
        "item_to_unlock": "BRONZE_KEY",
        "rule_to_unlock": "",
    }
    resp = await client.patch(
        f"/api/adventures/{adv_id}/editor/entity",
        headers=_auth_headers(user.username),
        json=payload,
    )
    assert resp.status_code == 200, resp.text

    async with TestSessionLocal() as db:
        from sqlalchemy import select as _sel

        res = await db.execute(_sel(WorldExit).where(WorldExit.id == exit_id))
        world_exit = res.scalars().first()
        assert world_exit is not None
        assert world_exit.label == "A locked door (renamed)"
        assert world_exit.lock_description == "Updated description."
        assert world_exit.code_to_unlock in ("", None)
        assert world_exit.item_to_unlock == "BRONZE_KEY"
        assert world_exit.rule_to_unlock in ("", None)
        assert world_exit.is_locked is True


async def test_exit_edit_lock_removal(client, setup_test_db):
    """Removing ALL lock keys (code, item, rule) on an edit should clear the lock."""
    user = User(username="exit_unlock_user", hashed_password="x", role="admin")
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        adv_id = "tpl-exit-unlock"
        tpl = AdventureTemplate(
            id=adv_id,
            owner_id=user.id,
            title="Unlock Test",
            version="1.0",
            rule_enforcement_mode="rpg",
            is_ready=True,
            creation_status="Ready",
            generate_scene_images=False,
            generate_npc_images=False,
            generate_item_images=False,
            teaser="t",
            rules="r",
            plot="p",
            intro_text="i",
            completed_condition="done",
            gameover_condition="lost",
            tts_director_notes="notes",
            quests=[],
        )
        db.add(tpl)
        db.add(WorldScene(id="SCENE_A", template_id=adv_id, label="A", description="A"))
        db.add(WorldScene(id="SCENE_B", template_id=adv_id, label="B", description="B"))
        db.add(
            WorldEntity(
                id="BRONZE_KEY",
                template_id=adv_id,
                entity_type="OBJECT",
                name="Bronze Key",
                description="Unlocks the door.",
                current_scene_id="SCENE_A",
            )
        )
        seeded_exit = WorldExit(
            template_id=adv_id,
            from_scene_id="SCENE_A",
            to_scene_id="SCENE_B",
            label="A locked door",
            is_locked=True,
            code_to_unlock="1331",
            exit_type="one_way",
        )
        db.add(seeded_exit)
        await db.commit()
        exit_id = seeded_exit.id

    payload = {
        "target_type": "exit",
        "target_id": exit_id,
        "name": "A locked door",
        "description": "",
        "exit_type": "one_way",
        "locked": False,
        "code_to_unlock": "",
        "item_to_unlock": "",
        "rule_to_unlock": "",
    }
    resp = await client.patch(
        f"/api/adventures/{adv_id}/editor/entity",
        headers=_auth_headers(user.username),
        json=payload,
    )
    assert resp.status_code == 200, resp.text

    async with TestSessionLocal() as db:
        from sqlalchemy import select as _sel

        res = await db.execute(_sel(WorldExit).where(WorldExit.id == exit_id))
        world_exit = res.scalars().first()
        assert world_exit.code_to_unlock in ("", None)
        assert world_exit.item_to_unlock in ("", None)
        assert world_exit.rule_to_unlock in ("", None)
        assert world_exit.is_locked is False


_LIFECYCLE_TEMPLATE_ID = "tpl-exit-type-lifecycle"


async def _seed_exit_type_adventure(owner_id: str) -> None:
    """Two rooms joined by a one-way exit EXIT_1, in both DB rows and the manifest."""
    adv_id = _LIFECYCLE_TEMPLATE_ID
    initial_manifest = {
        "format": "TaleWeaver",
        "version": "1.2",
        "adventure": {"title": "Exit Type Test"},
        "scenes": [
            {"id": "ROOM_1", "label": "Room 1", "description": "R1"},
            {"id": "ROOM_2", "label": "Room 2", "description": "R2"},
        ],
        "exits": [
            {
                "id": "EXIT_1",
                "from_scene_id": "ROOM_1",
                "to_scene_id": "ROOM_2",
                "label": "Passage",
                "exit_type": "one_way",
                "is_bidirectional": False,
                "is_locked": False,
            }
        ],
        "npcs": [],
        "objects": [],
    }
    async with TestSessionLocal() as db:
        db.add(
            AdventureTemplate(
                id=adv_id,
                owner_id=owner_id,
                title="Exit Type Test",
                version="1.0",
                rule_enforcement_mode="rpg",
                is_ready=True,
                creation_status="Ready",
                generate_scene_images=False,
                generate_npc_images=False,
                generate_item_images=False,
                teaser="t",
                original_manifest=initial_manifest,
                quests=[],
            )
        )
        db.add(WorldScene(id="ROOM_1", template_id=adv_id, label="Room 1", description="R1"))
        db.add(WorldScene(id="ROOM_2", template_id=adv_id, label="Room 2", description="R2"))
        db.add(
            WorldExit(
                id="EXIT_1",
                template_id=adv_id,
                from_scene_id="ROOM_1",
                to_scene_id="ROOM_2",
                label="Passage",
                is_locked=False,
                exit_type="one_way",
            )
        )
        await db.commit()


async def _set_exit_type(client, username: str, exit_type: str) -> None:
    resp = await client.patch(
        f"/api/adventures/{_LIFECYCLE_TEMPLATE_ID}/editor/entity",
        headers=_auth_headers(username),
        json={
            "target_type": "exit",
            "target_id": "EXIT_1",
            "name": "Passage",
            "exit_type": exit_type,
            "locked": False,
        },
    )
    assert resp.status_code == 200, resp.text


def _assert_single_exit(exits: list, exit_type: str) -> None:
    assert len(exits) == 1
    assert exits[0]["exit_type"] == exit_type
    assert exits[0]["is_bidirectional"] is (exit_type == "bidirectional")


async def _assert_exit_type_everywhere(exit_type: str) -> dict:
    """DB row, stored manifest and exported manifest agree; returns the export."""
    from sqlalchemy import select

    from backend.engine.adventures.adventure_exporter import AdventureExporter

    async with TestSessionLocal() as db:
        exit_row = (
            (await db.execute(select(WorldExit).where(WorldExit.id == "EXIT_1"))).scalars().first()
        )
        assert exit_row is not None
        assert exit_row.exit_type == exit_type

        adv_row = await db.get(AdventureTemplate, _LIFECYCLE_TEMPLATE_ID)
        _assert_single_exit(adv_row.original_manifest.get("exits", []), exit_type)

        exported = await AdventureExporter.build_full_manifest(db, _LIFECYCLE_TEMPLATE_ID)
        _assert_single_exit(exported.get("exits", []), exit_type)
        return exported


async def test_exit_type_edit_and_export_lifecycle(client, setup_test_db):
    """Changing exit_type to bidirectional in editor persists to DB, manifests, and survives export/import."""
    from sqlalchemy import select

    from backend.engine.world.world_manifest_applier import _persist_exits

    user = User(username="exit_type_user", hashed_password="x", role="admin")
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
    await _seed_exit_type_adventure(user.id)

    # 1. Edit to bidirectional; DB row, manifest and export follow.
    await _set_exit_type(client, user.username, "bidirectional")
    exported = await _assert_exit_type_everywhere("bidirectional")

    # 2. Re-importing the exported exits preserves the bidirectional type.
    new_template_id = "tpl-exit-reimported"
    async with TestSessionLocal() as db:
        _persist_exits(db, new_template_id, exported["exits"])
        await db.commit()
        result = await db.execute(select(WorldExit).where(WorldExit.template_id == new_template_id))
        reimported = result.scalars().all()
        assert len(reimported) == 1
        assert reimported[0].exit_type == "bidirectional"

    # 3. Switching back to one_way is reflected everywhere as well.
    await _set_exit_type(client, user.username, "one_way")
    await _assert_exit_type_everywhere("one_way")
