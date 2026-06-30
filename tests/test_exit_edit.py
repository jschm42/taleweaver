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
