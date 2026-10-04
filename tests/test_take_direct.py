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
async def test_take_direct_removes_from_scene_entities(client, setup_test_db):
    async with TestSessionLocal() as db_session:
        user = User(
            username="take_test_user",
            hashed_password="test_hash",
            role="admin",
        )
        db_session.add(user)
        await db_session.flush()

        template = AdventureTemplate(
            title="Test Take Direct",
            owner_id=user.id,
            version="2.0.0",
            sequences=[
                {
                    "id": "SEQ_1",
                    "title": "Sequence 1",
                    "order": 1,
                    "required_item_id": "GUEST_BADGE",
                    "exp_reward": 20,
                },
                {
                    "id": "SEQ_2",
                    "title": "Sequence 2",
                    "order": 2,
                },
            ],
            is_ready=True,
            creation_status="Ready",
            original_manifest={
                "version": "2.0.0",
                "format_version": "2.0.0",
                "sequences": [
                    {
                        "id": "SEQ_1",
                        "title": "Sequence 1",
                        "order": 1,
                        "required_item_id": "GUEST_BADGE",
                        "exp_reward": 20,
                    },
                    {
                        "id": "SEQ_2",
                        "title": "Sequence 2",
                        "order": 2,
                    },
                ],
                "start_scene_id": "LOBBY",
            },
        )
        db_session.add(template)
        await db_session.flush()

        scene = WorldScene(
            id="LOBBY",
            template_id=template.id,
            label="Lobby",
            description="The entrance.",
        )
        db_session.add(scene)

        avatar = Avatar(
            user_id=user.id,
            template_id=template.id,
            name="Hero",
            inventory=[],
        )
        db_session.add(avatar)

        badge = WorldEntity(
            id="GUEST_BADGE",
            template_id=template.id,
            entity_type="OBJECT",
            name="Visitor Lanyard Badge",
            description="A guest lanyard badge.",
            current_scene_id="LOBBY",
            is_portable=True,
            is_in_inventory=False,
            is_hidden=False,
        )
        db_session.add(badge)
        await db_session.commit()
        template_id = template.id

    headers = _auth_headers("take_test_user")

    # Start session
    start_res = await client.post(
        f"/api/adventures/{template_id}/sessions/start",
        headers=headers,
    )
    assert start_res.status_code == 201
    game_id = start_res.json()["game_id"]

    # Verify badge is in scene entities before take
    async with TestSessionLocal() as db_session:
        st_res = await db_session.execute(
            select(SessionState).where(SessionState.session_id == game_id)
        )
        st = st_res.scalars().first()
        scene_ents = await AdventureLogic.build_session_entities(db_session, st)
        ent_ids = [e["id"] for e in scene_ents]
        assert "GUEST_BADGE" in ent_ids

    # Send /take_direct GUEST_BADGE
    chat_res = await client.post(
        f"/api/adventures/{game_id}/chat",
        headers=headers,
        json={"content": "/take_direct GUEST_BADGE"},
    )
    assert chat_res.status_code == 200

    # Verify badge is NO LONGER in scene entities
    async with TestSessionLocal() as db_session:
        st_res = await db_session.execute(
            select(SessionState).where(SessionState.session_id == game_id)
        )
        st = st_res.scalars().first()
        scene_ents = await AdventureLogic.build_session_entities(db_session, st)
        ent_ids = [e["id"] for e in scene_ents]
        assert "GUEST_BADGE" not in ent_ids

        # Verify avatar has exactly 1 badge and earned 20 XP from SEQ_1 completion
        av_res = await db_session.execute(
            select(Avatar).where(Avatar.id == st.avatar_id)
        )
        av = av_res.scalars().first()
        inv_badges = [i for i in (av.inventory or []) if (i.get("id") if isinstance(i, dict) else i) == "GUEST_BADGE"]
        assert len(inv_badges) == 1
        assert av.exp == 20
        assert st.active_sequence_id == "SEQ_2"

    # Verify get_chat returns active_sequence as SEQ_2
    chat_state_res = await client.get(
        f"/api/adventures/{game_id}/chat",
        headers=headers,
    )
    assert chat_state_res.status_code == 200
    chat_state = chat_state_res.json()
    assert chat_state["active_sequence"]["id"] == "SEQ_2"
    assert chat_state["sheet"]["exp"] == 20

    # Send /take_direct GUEST_BADGE again
    chat_res2 = await client.post(
        f"/api/adventures/{game_id}/chat",
        headers=headers,
        json={"content": "/take_direct GUEST_BADGE"},
    )
    assert chat_res2.status_code == 200

    async with TestSessionLocal() as db_session:
        av_res = await db_session.execute(
            select(Avatar).where(Avatar.id == st.avatar_id)
        )
        av = av_res.scalars().first()
        inv_badges = [i for i in (av.inventory or []) if (i.get("id") if isinstance(i, dict) else i) == "GUEST_BADGE"]
        assert len(inv_badges) == 1
        assert av.exp == 20
