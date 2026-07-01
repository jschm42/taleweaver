import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from backend.models.avatar import Avatar
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldEntity
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def test_unlock_container_with_item(auth_client: AsyncClient, setup_test_db):
    # Create adventure/session
    resp = await auth_client.post(
        "/api/adventures/",
        json={"title": "Unlock Quest", "avatar_name": "Hero", "skip_generation": True},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    game_id = data["game_id"]
    avatar_id = data["avatar_id"]

    # Inject a locked container and a key into the session
    async with TestSessionLocal() as db:
        container = WorldEntity(
            id="locked_chest",
            session_id=game_id,
            entity_type="OBJECT",
            item_type="CONTAINER",
            name="Locked Chest",
            description="A locked chest.",
            current_scene_id="START",
            metadata_json={"item_to_unlock": "BRONZE_KEY", "locked": True}
        )
        db.add(container)

        state_res = await db.execute(select(SessionState).where(SessionState.session_id == game_id))
        state = state_res.scalars().first()
        state.entity_states = {"locked_chest": {"locked": True}}
        flag_modified(state, "entity_states")

        avatar_res = await db.execute(select(Avatar).where(Avatar.id == avatar_id))
        avatar = avatar_res.scalars().first()
        avatar.inventory = [{"id": "BRONZE_KEY", "name": "Bronze Key", "item_type": "PICKABLE"}]
        flag_modified(avatar, "inventory")

        await db.commit()

    # 1. Attempt to unlock with incorrect item
    resp = await auth_client.post(
        f"/api/adventures/{game_id}/containers/locked_chest/unlock-item",
        json={"item_id": "SILVER_KEY"}
    )
    assert resp.status_code == 403, resp.text

    # 2. Attempt to unlock with correct item but not in inventory
    async with TestSessionLocal() as db:
        avatar_res = await db.execute(select(Avatar).where(Avatar.id == avatar_id))
        avatar = avatar_res.scalars().first()
        avatar.inventory = []
        flag_modified(avatar, "inventory")
        await db.commit()

    resp = await auth_client.post(
        f"/api/adventures/{game_id}/containers/locked_chest/unlock-item",
        json={"item_id": "BRONZE_KEY"}
    )
    assert resp.status_code == 403, resp.text

    # 3. Unlock successfully with correct item in inventory
    async with TestSessionLocal() as db:
        avatar_res = await db.execute(select(Avatar).where(Avatar.id == avatar_id))
        avatar = avatar_res.scalars().first()
        avatar.inventory = [{"id": "BRONZE_KEY", "name": "Bronze Key", "item_type": "PICKABLE"}]
        flag_modified(avatar, "inventory")
        await db.commit()

    resp = await auth_client.post(
        f"/api/adventures/{game_id}/containers/locked_chest/unlock-item",
        json={"item_id": "BRONZE_KEY"}
    )
    assert resp.status_code == 200, resp.text
    res_data = resp.json()
    assert res_data["locked"] is False

    # Verify database state was updated
    async with TestSessionLocal() as db:
        state_res = await db.execute(select(SessionState).where(SessionState.session_id == game_id))
        state = state_res.scalars().first()
        assert state.entity_states["locked_chest"]["locked"] is False
