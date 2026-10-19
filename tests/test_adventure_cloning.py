import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from backend.core.config import settings
from backend.main import app
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene
from backend.models.world_map import WorldMap
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def setup_adventure_data():
    """Sets up a complete adventure template with scenes, exits, entities, and disk assets."""
    async with TestSessionLocal() as db:
        user = User(
            username="cloner_user",
            hashed_password="pw",
            role="user",
        )
        other_user = User(
            username="other_user",
            hashed_password="pw",
            role="user",
        )
        db.add_all([user, other_user])
        await db.commit()
        await db.refresh(user)
        await db.refresh(other_user)

        template = AdventureTemplate(
            id="adv-cloner-test-1",
            title="Mystic Cavern",
            owner_id=user.id,
            origin_id="sample-origin-123",
            teaser="A mysterious underground cavern.",
            version="1.2.0",
            image_url="/data/adventures/library/adv-cloner-test-1/cover.png",
            is_ready=True,
            original_manifest={
                "format": "TaleWeaver",
                "version": "1.0.0",
                "adventure": {
                    "title": "Mystic Cavern",
                    "image_url": "/data/adventures/library/adv-cloner-test-1/cover.png",
                },
                "protagonist": {
                    "name": "Explorer",
                    "profile_image": "/data/adventures/library/adv-cloner-test-1/hero.png",
                },
                "scenes": [
                    {
                        "id": "CAVE_ENTRANCE",
                        "image_url": "/data/adventures/library/adv-cloner-test-1/scenes/entrance.png",
                    }
                ],
                "npcs": [
                    {
                        "id": "CAVE_BAT",
                        "image_url": "/data/adventures/library/adv-cloner-test-1/entities/bat.png",
                    }
                ],
            },
        )
        db.add(template)

        # Add avatar
        avatar = Avatar(
            template_id="adv-cloner-test-1",
            user_id=user.id,
            name="Explorer",
            role="Protagonist",
            profile_image="/data/adventures/library/adv-cloner-test-1/hero.png",
            stats={"str": 12, "dex": 14},
        )
        db.add(avatar)

        # Add scene
        scene = WorldScene(
            id="CAVE_ENTRANCE",
            template_id="adv-cloner-test-1",
            label="Cave Entrance",
            description="The dark mouth of the cavern.",
            image_url="/data/adventures/library/adv-cloner-test-1/scenes/entrance.png",
        )
        scene2 = WorldScene(
            id="CAVE_DEPTHS",
            template_id="adv-cloner-test-1",
            label="Cave Depths",
            description="Deeper inside the darkness.",
        )
        db.add_all([scene, scene2])

        # Add exit
        exit_conn = WorldExit(
            template_id="adv-cloner-test-1",
            from_scene_id="CAVE_ENTRANCE",
            to_scene_id="CAVE_DEPTHS",
            label="A dark opening leading down",
        )
        db.add(exit_conn)

        # Add entities (NPC and object)
        npc = WorldEntity(
            id="CAVE_BAT",
            template_id="adv-cloner-test-1",
            entity_type="NPC",
            name="Giant Bat",
            description="A screeching bat hangs from stalactites.",
            current_scene_id="CAVE_ENTRANCE",
            image_url="/data/adventures/library/adv-cloner-test-1/entities/bat.png",
        )
        obj = WorldEntity(
            id="GOLD_COIN",
            template_id="adv-cloner-test-1",
            entity_type="OBJECT",
            name="Ancient Coin",
            description="A glittering old coin on the ground.",
            current_scene_id="CAVE_ENTRANCE",
        )
        db.add_all([npc, obj])

        # Add world map
        wm = WorldMap(
            template_id="adv-cloner-test-1",
            nodes={"CAVE_ENTRANCE": {"label": "Cave Entrance"}},
            edges=[],
        )
        db.add(wm)

        # Public sample adventure (owner_id = None)
        sample = AdventureTemplate(
            id="sample-adv-1",
            title="Public Tutorial",
            owner_id=None,
            is_ready=True,
        )
        db.add(sample)

        await db.commit()

        # Create dummy assets in DATA_DIR
        lib_dir = os.path.join(settings.DATA_DIR, "adventures", "library", "adv-cloner-test-1")
        os.makedirs(os.path.join(lib_dir, "scenes"), exist_ok=True)
        with open(os.path.join(lib_dir, "cover.png"), "wb") as f:
            f.write(b"fake cover image")
        with open(os.path.join(lib_dir, "scenes", "entrance.png"), "wb") as f:
            f.write(b"fake scene image")

        return {
            "user_id": user.id,
            "other_user_id": other_user.id,
            "template_id": template.id,
            "sample_id": sample.id,
        }


async def test_duplicate_adventure_success(setup_test_db, setup_adventure_data, monkeypatch):
    """Verify that an adventure is fully duplicated with all entities, URLs rewritten, and assets copied."""
    from backend.core.auth import get_current_user

    data = setup_adventure_data

    async with TestSessionLocal() as db:
        user = await db.scalar(select(User).where(User.id == data["user_id"]))
        app.dependency_overrides[get_current_user] = lambda: user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/api/adventures/{data['template_id']}/duplicate")
            assert resp.status_code == 201, resp.text
            res_data = resp.json()

            new_id = res_data["id"]
            assert new_id != data["template_id"]
            assert res_data["title"] == "Mystic Cavern (Copy)"
            assert res_data["origin_id"] is None
            assert res_data["image_url"] == f"/data/adventures/library/{new_id}/cover.png"

            # Check database records
            cloned_template = await db.scalar(
                select(AdventureTemplate).where(AdventureTemplate.id == new_id)
            )
            assert cloned_template is not None
            assert cloned_template.owner_id == data["user_id"]

            # Check cloned avatar
            cloned_avatars = (
                await db.scalars(select(Avatar).where(Avatar.template_id == new_id))
            ).all()
            assert len(cloned_avatars) == 1
            assert cloned_avatars[0].name == "Explorer"
            assert cloned_avatars[0].profile_image == f"/data/adventures/library/{new_id}/hero.png"

            # Check cloned scenes
            cloned_scenes = (
                await db.scalars(select(WorldScene).where(WorldScene.template_id == new_id))
            ).all()
            assert len(cloned_scenes) == 2
            entrance_scene = next(s for s in cloned_scenes if s.id == "CAVE_ENTRANCE")
            assert (
                entrance_scene.image_url == f"/data/adventures/library/{new_id}/scenes/entrance.png"
            )

            # Check cloned exits
            cloned_exits = (
                await db.scalars(select(WorldExit).where(WorldExit.template_id == new_id))
            ).all()
            assert len(cloned_exits) == 1
            assert cloned_exits[0].from_scene_id == "CAVE_ENTRANCE"
            assert cloned_exits[0].to_scene_id == "CAVE_DEPTHS"

            # Check cloned entities
            cloned_entities = (
                await db.scalars(select(WorldEntity).where(WorldEntity.template_id == new_id))
            ).all()
            assert len(cloned_entities) == 2
            bat = next(e for e in cloned_entities if e.id == "CAVE_BAT")
            assert bat.image_url == f"/data/adventures/library/{new_id}/entities/bat.png"

            # Check cloned map
            cloned_maps = (
                await db.scalars(select(WorldMap).where(WorldMap.template_id == new_id))
            ).all()
            assert len(cloned_maps) == 1

            # Check copied assets on disk
            new_lib_dir = os.path.join(settings.DATA_DIR, "adventures", "library", new_id)
            assert os.path.isfile(os.path.join(new_lib_dir, "cover.png"))
            assert os.path.isfile(os.path.join(new_lib_dir, "scenes", "entrance.png"))

        app.dependency_overrides.clear()


async def test_duplicate_adventure_multiple_copies(setup_test_db, setup_adventure_data):
    """Verify that multiple duplicates of the same adventure receive incremented copy numbers."""
    from backend.core.auth import get_current_user

    data = setup_adventure_data

    async with TestSessionLocal() as db:
        user = await db.scalar(select(User).where(User.id == data["user_id"]))
        app.dependency_overrides[get_current_user] = lambda: user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp1 = await client.post(f"/api/adventures/{data['template_id']}/duplicate")
            assert resp1.status_code == 201
            assert resp1.json()["title"] == "Mystic Cavern (Copy)"

            resp2 = await client.post(f"/api/adventures/{data['template_id']}/duplicate")
            assert resp2.status_code == 201
            assert resp2.json()["title"] == "Mystic Cavern (Copy 2)"

            resp3 = await client.post(f"/api/adventures/{data['template_id']}/duplicate")
            assert resp3.status_code == 201
            assert resp3.json()["title"] == "Mystic Cavern (Copy 3)"

        app.dependency_overrides.clear()


async def test_duplicate_adventure_custom_title(setup_test_db, setup_adventure_data):
    """Verify that a custom title provided in payload is applied."""
    from backend.core.auth import get_current_user

    data = setup_adventure_data

    async with TestSessionLocal() as db:
        user = await db.scalar(select(User).where(User.id == data["user_id"]))
        app.dependency_overrides[get_current_user] = lambda: user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/adventures/{data['template_id']}/duplicate",
                json={"title": "Custom Underworld"},
            )
            assert resp.status_code == 201
            assert resp.json()["title"] == "Custom Underworld"

        app.dependency_overrides.clear()


async def test_duplicate_adventure_sample_adventure(setup_test_db, setup_adventure_data):
    """Verify that a public sample adventure (owner_id is None) can be duplicated by a user."""
    from backend.core.auth import get_current_user

    data = setup_adventure_data

    async with TestSessionLocal() as db:
        user = await db.scalar(select(User).where(User.id == data["user_id"]))
        app.dependency_overrides[get_current_user] = lambda: user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/api/adventures/{data['sample_id']}/copy")
            assert resp.status_code == 201
            res_data = resp.json()
            assert res_data["title"] == "Public Tutorial (Copy)"

            # Owner should now be this user
            cloned = await db.scalar(
                select(AdventureTemplate).where(AdventureTemplate.id == res_data["id"])
            )
            assert cloned.owner_id == user.id

        app.dependency_overrides.clear()


async def test_duplicate_adventure_unauthorized(setup_test_db, setup_adventure_data):
    """Verify that another user cannot duplicate a private adventure belonging to someone else."""
    from backend.core.auth import get_current_user

    data = setup_adventure_data

    async with TestSessionLocal() as db:
        other_user = await db.scalar(select(User).where(User.id == data["other_user_id"]))
        app.dependency_overrides[get_current_user] = lambda: other_user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/api/adventures/{data['template_id']}/duplicate")
            assert resp.status_code == 404

        app.dependency_overrides.clear()


async def test_duplicate_adventure_not_found(setup_test_db, setup_adventure_data):
    """Verify that trying to duplicate a non-existent adventure returns 404."""
    from backend.core.auth import get_current_user

    data = setup_adventure_data

    async with TestSessionLocal() as db:
        user = await db.scalar(select(User).where(User.id == data["user_id"]))
        app.dependency_overrides[get_current_user] = lambda: user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/adventures/non-existent-adventure-id/duplicate")
            assert resp.status_code == 404

        app.dependency_overrides.clear()


async def test_duplicate_adventure_long_title_truncation(setup_test_db):
    """Verify that cloning an adventure with a title near the 50-character limit keeps the clone title <= 50 chars."""
    from backend.core.auth import get_current_user

    async with TestSessionLocal() as db:
        user = User(username="long_title_user", hashed_password="pw", role="user")
        db.add(user)
        await db.commit()
        await db.refresh(user)

        # 48 character title
        long_title = "The Chronicles of the Forgotten Realm of Eternity"
        assert len(long_title) == 49
        template = AdventureTemplate(
            id="adv-long-title-test",
            title=long_title,
            owner_id=user.id,
            is_ready=True,
        )
        db.add(template)
        await db.commit()

        app.dependency_overrides[get_current_user] = lambda: user
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/api/adventures/{template.id}/duplicate")
            assert resp.status_code == 201
            cloned_title = resp.json()["title"]
            assert len(cloned_title) <= 50
            assert cloned_title.endswith("(Copy)")

        app.dependency_overrides.clear()
