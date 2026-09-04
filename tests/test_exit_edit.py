"""Tests for the exit update path used by EditExitModal."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth import create_access_token
from backend.main import app
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene
from backend.models.base import Base
from backend.core.database import get_db
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
            walkthrough="w",
            completed_condition="done",
            gameover_condition="lost",
            tts_director_notes="notes",
            quests=[],
        )
        db.add(tpl)
        db.add(WorldScene(id="SCENE_A", template_id=adv_id, label="A", description="A"))
        db.add(WorldScene(id="SCENE_B", template_id=adv_id, label="B", description="B"))
        db.add(WorldEntity(
            id="BRONZE_KEY",
            template_id=adv_id,
            entity_type="OBJECT",
            name="Bronze Key",
            description="Unlocks the door.",
            current_scene_id="SCENE_A",
            item_type="DEFAULT",
        ))
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
        res = await db.execute(
            _sel(WorldExit).where(WorldExit.id == exit_id)
        )
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
            walkthrough="w",
            completed_condition="done",
            gameover_condition="lost",
            tts_director_notes="notes",
            quests=[],
        )
        db.add(tpl)
        db.add(WorldScene(id="SCENE_A", template_id=adv_id, label="A", description="A"))
        db.add(WorldScene(id="SCENE_B", template_id=adv_id, label="B", description="B"))
        db.add(WorldEntity(
            id="BRONZE_KEY",
            template_id=adv_id,
            entity_type="OBJECT",
            name="Bronze Key",
            description="Unlocks the door.",
            current_scene_id="SCENE_A",
        ))
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
        res = await db.execute(
            _sel(WorldExit).where(WorldExit.id == exit_id)
        )
        world_exit = res.scalars().first()
        assert world_exit.code_to_unlock in ("", None)
        assert world_exit.item_to_unlock in ("", None)
        assert world_exit.rule_to_unlock in ("", None)
        assert world_exit.is_locked is False


async def test_exit_type_edit_and_export_lifecycle(client, setup_test_db):
    """Changing exit_type to bidirectional in editor persists to DB, manifests, and survives export/import."""
    from backend.engine.adventure_exporter import AdventureExporter
    from backend.engine.world_manifest_applier import _persist_exits

    user = User(username="exit_type_user", hashed_password="x", role="admin")
    adv_id = "tpl-exit-type-lifecycle"

    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()

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

        tpl = AdventureTemplate(
            id=adv_id,
            owner_id=user.id,
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
        db.add(tpl)
        db.add(WorldScene(id="ROOM_1", template_id=adv_id, label="Room 1", description="R1"))
        db.add(WorldScene(id="ROOM_2", template_id=adv_id, label="Room 2", description="R2"))

        seeded_exit = WorldExit(
            id="EXIT_1",
            template_id=adv_id,
            from_scene_id="ROOM_1",
            to_scene_id="ROOM_2",
            label="Passage",
            is_locked=False,
            exit_type="one_way",
        )
        db.add(seeded_exit)
        await db.commit()

    # 1. Edit exit to 'bidirectional' via editor API
    patch_payload = {
        "target_type": "exit",
        "target_id": "EXIT_1",
        "name": "Passage",
        "exit_type": "bidirectional",
        "locked": False,
    }
    resp = await client.patch(
        f"/api/adventures/{adv_id}/editor/entity",
        headers=_auth_headers(user.username),
        json=patch_payload,
    )
    assert resp.status_code == 200, resp.text

    # 2. Check DB row and original_manifest updated
    async with TestSessionLocal() as db:
        from sqlalchemy import select as _sel
        res = await db.execute(_sel(WorldExit).where(WorldExit.id == "EXIT_1"))
        exit_row = res.scalars().first()
        assert exit_row is not None
        assert exit_row.exit_type == "bidirectional"

        adv_res = await db.execute(_sel(AdventureTemplate).where(AdventureTemplate.id == adv_id))
        adv_row = adv_res.scalars().first()
        manifest_exits = adv_row.original_manifest.get("exits", [])
        assert len(manifest_exits) == 1
        assert manifest_exits[0]["exit_type"] == "bidirectional"
        assert manifest_exits[0]["is_bidirectional"] is True

        # 3. Test AdventureExporter.build_full_manifest
        exported = await AdventureExporter.build_full_manifest(db, adv_id)
        exp_exits = exported.get("exits", [])
        assert len(exp_exits) == 1
        assert exp_exits[0]["exit_type"] == "bidirectional"
        assert exp_exits[0]["is_bidirectional"] is True

    # 4. Test re-importing the exported manifest preserves bidirectional exit
    new_template_id = "tpl-exit-reimported"
    async with TestSessionLocal() as db:
        _persist_exits(db, new_template_id, exported["exits"])
        await db.commit()

        reimp_res = await db.execute(_sel(WorldExit).where(WorldExit.template_id == new_template_id))
        reimp_exits = reimp_res.scalars().all()
        assert len(reimp_exits) == 1
        assert reimp_exits[0].exit_type == "bidirectional"

    # 5. Change exit back to 'one_way' via editor API
    patch_payload_oneway = {
        "target_type": "exit",
        "target_id": "EXIT_1",
        "name": "Passage",
        "exit_type": "one_way",
        "locked": False,
    }
    resp2 = await client.patch(
        f"/api/adventures/{adv_id}/editor/entity",
        headers=_auth_headers(user.username),
        json=patch_payload_oneway,
    )
    assert resp2.status_code == 200, resp2.text

    async with TestSessionLocal() as db:
        res2 = await db.execute(_sel(WorldExit).where(WorldExit.id == "EXIT_1"))
        exit_row2 = res2.scalars().first()
        assert exit_row2 is not None
        assert exit_row2.exit_type == "one_way"

        exported2 = await AdventureExporter.build_full_manifest(db, adv_id)
        exp_exits2 = exported2.get("exits", [])
        assert len(exp_exits2) == 1
        assert exp_exits2[0]["exit_type"] == "one_way"
        assert exp_exits2[0]["is_bidirectional"] is False

