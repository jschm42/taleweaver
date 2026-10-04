import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from backend.core.auth import create_access_token
from backend.core.database import get_db
from backend.main import app
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldScene
from backend.api.routes.adventures.logic import AdventureLogic
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


@pytest.mark.asyncio
async def test_editor_inventory_to_scene_sync(client, setup_test_db):
    async with TestSessionLocal() as db_session:
        user = User(
            username="editor_user",
            hashed_password="test_hash",
            role="admin",
        )
        db_session.add(user)
        await db_session.flush()

        template = AdventureTemplate(
            title="Test Inventory Sync",
            owner_id=user.id,
            version="2.0.0",
            sequences=[{"id": "SEQ_1", "title": "Sequence 1"}],
            is_ready=True,
            creation_status="Ready",
            original_manifest={
                "version": "2.0.0",
                "format_version": "2.0.0",
                "sequences": [{"id": "SEQ_1", "title": "Sequence 1"}],
                "protagonist": {"name": "Hero", "starting_inventory": ["KEY_1"]},
                "start_scene_id": "ROOM_A",
            },
        )
        db_session.add(template)
        await db_session.flush()

        scene = WorldScene(
            id="ROOM_A",
            template_id=template.id,
            label="Room A",
            description="A quiet room.",
        )
        db_session.add(scene)

        avatar = Avatar(
            user_id=user.id,
            template_id=template.id,
            name="Hero",
            inventory=[{"id": "KEY_1", "name": "Key One"}],
        )
        db_session.add(avatar)

        entity = WorldEntity(
            id="KEY_1",
            template_id=template.id,
            entity_type="OBJECT",
            name="Key One",
            description="A small brass key.",
            current_scene_id="INVENTORY",
            is_in_inventory=True,
        )
        db_session.add(entity)
        await db_session.commit()

        template_id = template.id
        entity_pk = entity.pk
        avatar_id = avatar.id

    headers = _auth_headers("editor_user")

    # 1. Act: Move entity to ROOM_A via editor PATCH endpoint
    res = await client.patch(
        f"/api/adventures/{template_id}/editor/entity",
        headers=headers,
        json={
            "target_type": "object",
            "target_id": "KEY_1",
            "current_scene_id": "ROOM_A",
        },
    )
    assert res.status_code == 200

    # 2. Assert: Entity is now in ROOM_A with is_in_inventory=False, and removed from avatar
    async with TestSessionLocal() as db_session:
        ent = await db_session.get(WorldEntity, entity_pk)
        av = await db_session.get(Avatar, avatar_id)
        assert ent.current_scene_id == "ROOM_A"
        assert ent.is_in_inventory is False
        assert not any(
            (i if isinstance(i, str) else i.get("id")) == "KEY_1"
            for i in (av.inventory or [])
        )

    # 3. Act: Start a new session for this template
    start_res = await client.post(
        f"/api/adventures/{template_id}/sessions/start",
        headers=headers,
    )
    assert start_res.status_code == 201, start_res.text
    game_id = start_res.json()["game_id"]

    # 4. Assert: Entity in new session has is_in_inventory=False and is returned by build_session_entities
    async with TestSessionLocal() as db_session:
        st_res = await db_session.execute(
            select(SessionState).where(SessionState.session_id == game_id)
        )
        session_state = st_res.scalars().first()
        assert session_state is not None

        session_entities = await AdventureLogic.build_session_entities(db_session, session_state)
        returned_ids = [e["id"] for e in session_entities]
        assert "KEY_1" in returned_ids
