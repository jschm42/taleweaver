import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from backend.core.auth import create_access_token
from backend.core.database import get_db
from backend.main import app
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.user import User
from backend.models.world_entity import WorldScene
from tests.conftest import TestSessionLocal


async def override_get_db():
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture
async def client():
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_session_scene_copy_keeps_scene_scripts(client, setup_test_db):
    # Arrange
    async with TestSessionLocal() as db:
        user = User(username="scene_script_user", hashed_password="x", role="admin")
        db.add(user)
        await db.flush()
        template = AdventureTemplate(
            title="Scene Scripts",
            owner_id=user.id,
            version="2.0.0",
            sequences=[{"id": "SEQ_1", "title": "Sequence 1"}],
            is_ready=True,
            creation_status="Ready",
            original_manifest={
                "version": "2.0.0",
                "format_version": "2.0.0",
                "sequences": [{"id": "SEQ_1", "title": "Sequence 1"}],
                "protagonist": {"name": "Hero"},
                "start_scene_id": "HALL",
            },
        )
        db.add(template)
        await db.flush()
        db.add(Avatar(user_id=user.id, template_id=template.id, name="Hero"))
        db.add(
            WorldScene(
                id="HALL",
                template_id=template.id,
                label="Hall",
                description="A hall.",
                decorative_objects=["dusty banner"],
                on_enter_scene_script="tw.vars.set('entered', True)",
                on_enter_scene_text="The doors creak.",
                on_leave_scene_script="tw.vars.set('left', True)",
                on_leave_scene_text="Cold air follows you.",
                helpers_script="def greet():\n    return 'hi'\n",
            )
        )
        await db.commit()
        template_id = template.id

    token = create_access_token(data={"sub": "scene_script_user"})

    # Act
    res = await client.post(
        f"/api/adventures/{template_id}/sessions/start",
        headers={"Authorization": f"Bearer {token}"},
    )

    # Assert
    assert res.status_code == 201, res.text
    async with TestSessionLocal() as db:
        scene = (
            await db.execute(
                select(WorldScene).where(WorldScene.session_id == res.json()["game_id"])
            )
        ).scalar_one()
        assert scene.on_enter_scene_script == "tw.vars.set('entered', True)"
        assert scene.on_enter_scene_text == "The doors creak."
        assert scene.on_leave_scene_script == "tw.vars.set('left', True)"
        assert scene.on_leave_scene_text == "Cold air follows you."
        assert scene.decorative_objects == ["dusty banner"]
        assert scene.helpers_script == "def greet():\n    return 'hi'\n"
