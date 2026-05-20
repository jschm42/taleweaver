import io
import json
import os
import zipfile
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.engine.session_exporter import SessionExporter
from backend.engine.session_importer import SessionImporter
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.chat import ChatMessage
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene
from backend.models.world_map import WorldMap

pytestmark = pytest.mark.asyncio


async def _seed_session_and_adventure(db: AsyncSession, user_id: str) -> tuple[str, str]:
    """Seeds a full adventure template and game session with all entity types."""
    adv = AdventureTemplate(
        id="test-session-template-123",
        owner_id=user_id,
        title="Session Lifecycle Test Adventure",
        teaser="A test for session export and import.",
        original_prompt="Prompt here",
        plot="Test plot",
        rules="Test rules",
        intro_text="Intro",
        completed_condition="Win",
        gameover_condition="Lose",
        starting_timestamp=480,
        image_url="/data/adventures/test-session-template-123/cover.jpg",
        is_ready=True,
    )
    db.add(adv)
    await db.flush()

    avatar = Avatar(
        id="test-session-avatar-123",
        template_id=adv.id,
        user_id=user_id,
        name="Test Session Protagonist",
        role="Tester",
        description="A hero for testing.",
        profile_image="/data/adventures/sessions/test-session-123/avatar.jpg",
        stats={"str": 15},
        inventory=[{"id": "POTION_1", "name": "Test Potion"}],
        equipment={"MainHand": {"id": "SWORD_1", "name": "Test Sword"}},
    )
    db.add(avatar)
    await db.flush()

    game_session = GameSession(
        id="test-session-123",
        user_id=user_id,
        avatar_id=avatar.id,
        template_id=adv.id,
        adventure_title="Session Lifecycle Test Adventure",
        adventure_image_url="/data/adventures/test-session-template-123/cover.jpg",
        status="active",
        status_note="This is a test note for game session.",
    )
    db.add(game_session)
    await db.flush()

    session_state = SessionState(
        session_id=game_session.id,
        user_id=user_id,
        template_id=adv.id,
        avatar_id=avatar.id,
        current_scene_id="SCENE_1",
        in_game_time=120,
        inventory=["POTION_1"],
        entity_states={"__asset_snapshot__": {"scene1": "/data/adventures/sessions/test-session-123/scenes/scene1.jpg"}},
        exit_states={},
        discovered_scenes=["SCENE_1"],
        quests=[{"id": "QUEST_1", "title": "First Quest", "status": "completed"}],
        is_completed=False,
    )
    db.add(session_state)

    scene = WorldScene(
        id="SCENE_1",
        template_id=adv.id,
        session_id=game_session.id,
        label="Test Session Scene",
        description="A scene for session testing.",
        image_url="/data/adventures/sessions/test-session-123/scene1.jpg",
    )
    db.add(scene)

    chat_message = ChatMessage(
        id="test-msg-123",
        session_id=game_session.id,
        role="assistant",
        content="Welcome to the lifecycle test.",
    )
    db.add(chat_message)

    npc = WorldEntity(
        id="NPC_1",
        template_id=adv.id,
        session_id=game_session.id,
        entity_type="NPC",
        name="Test NPC",
        description="An NPC for testing.",
        current_scene_id="SCENE_1",
        image_url="/data/adventures/sessions/test-session-123/npc1.jpg",
    )
    db.add(npc)

    obj = WorldEntity(
        id="SWORD_1",
        template_id=adv.id,
        session_id=game_session.id,
        entity_type="OBJECT",
        name="Test Sword",
        description="A sword for testing.",
        current_scene_id="INVENTORY",
        item_type="WEAPON",
    )
    db.add(obj)

    world_exit = WorldExit(
        id="exit-123",
        template_id=adv.id,
        session_id=game_session.id,
        from_scene_id="SCENE_1",
        to_scene_id="SCENE_2",
        label="Go east",
        is_locked=False,
    )
    db.add(world_exit)

    world_map = WorldMap(
        id="map-123",
        template_id=adv.id,
        session_id=game_session.id,
        nodes={"SCENE_1": {"label": "Start"}},
        edges=[],
        current_scene_id="SCENE_1",
    )
    db.add(world_map)

    await db.commit()
    return game_session.id, adv.id


async def test_session_ads_export_import_cycle(auth_client, setup_test_db, monkeypatch):
    """Verifies that a game session can be exported to .ads and imported back with all records intact."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user_res = await db.execute(select(User).limit(1))
        user = user_res.scalars().first()
        session_id, template_id = await _seed_session_and_adventure(db, user.id)

        # Mock filesystem path presence
        original_exists = os.path.exists

        def fake_exists(path):
            if "avatar.jpg" in path or "scene1.jpg" in path or "npc1.jpg" in path:
                return True
            return original_exists(path)

        monkeypatch.setattr("os.path.exists", fake_exists)

        # Mock zipfile.write to avoid actual file access
        def fake_zip_write(self, filename, arcname=None, compress_type=None):
            pass

        monkeypatch.setattr("zipfile.ZipFile.write", fake_zip_write)

        # Mock os.walk
        original_walk = os.walk

        def fake_walk(top, topdown=True, onerror=None, followlinks=False):
            if "test-session-123" in top:
                yield (top, [], ["avatar.jpg", "scene1.jpg", "npc1.jpg"])
            else:
                yield from original_walk(top, topdown, onerror, followlinks)

        monkeypatch.setattr("os.walk", fake_walk)
        monkeypatch.setattr("os.makedirs", lambda *args, **kwargs: None)

        # Export session
        ads_bytes = await SessionExporter.export_ads(db, session_id)
        assert len(ads_bytes) > 0

        # Verify ZIP contents
        with zipfile.ZipFile(io.BytesIO(ads_bytes)) as z:
            assert "session.json" in z.namelist()
            manifest = json.loads(z.read("session.json"))

            assert manifest["format"] == "TaleWeaverSession"
            assert manifest["game_session"]["status_note"] == "This is a test note for game session."
            assert manifest["avatar"]["name"] == "Test Session Protagonist"
            assert manifest["avatar"]["profile_image"] == "assets/avatar.jpg"
            assert manifest["session_state"]["in_game_time"] == 120
            assert manifest["session_state"]["entity_states"]["__asset_snapshot__"]["scene1"] == "assets/scenes/scene1.jpg"
            assert len(manifest["chat_messages"]) == 1
            assert manifest["chat_messages"][0]["content"] == "Welcome to the lifecycle test."
            assert len(manifest["world_scenes"]) == 1
            assert manifest["world_scenes"][0]["image_url"] == "assets/scene1.jpg"
            assert len(manifest["world_entities"]) == 2
            assert len(manifest["world_exits"]) == 1
            assert manifest["world_map"] is not None

        # 2. Import
        # Mock zip_file.read to return fake binary data for files other than session.json
        original_zip_read = zipfile.ZipFile.read

        def fake_zip_read(self, name):
            if name == "session.json":
                return original_zip_read(self, name)
            return b"fake_media_bytes"

        monkeypatch.setattr("zipfile.ZipFile.read", fake_zip_read)

        # Mock builtins.open
        import builtins
        original_open = builtins.open
        mock_files = {}

        class MockFile:
            def __init__(self, name):
                self.name = name

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def write(self, data):
                mock_files[self.name] = data

        def fake_open(name, mode="r", *args, **kwargs):
            if "wb" in mode:
                return MockFile(name)
            return original_open(name, mode, *args, **kwargs)

        monkeypatch.setattr("builtins.open", fake_open)

        # Import session
        new_session_id = await SessionImporter.import_ads(db, ads_bytes, owner_id=user.id)
        assert new_session_id is not None
        assert new_session_id != session_id

        # Verify imported database records in a new session query
        res = await db.execute(select(GameSession).where(GameSession.id == new_session_id))
        new_session = res.scalars().first()
        assert new_session is not None
        assert new_session.status_note == "This is a test note for game session."
        assert new_session.template_id == template_id

        # Check that state exists
        state_res = await db.execute(select(SessionState).where(SessionState.session_id == new_session_id))
        new_state = state_res.scalars().first()
        assert new_state is not None
        assert new_state.in_game_time == 120
        # Verify localized asset paths got updated to the new session prefix
        assert f"/data/adventures/sessions/{new_session_id}/" in new_state.entity_states["__asset_snapshot__"]["scene1"]

        # Check ChatMessage exists
        chat_res = await db.execute(select(ChatMessage).where(ChatMessage.session_id == new_session_id))
        messages = chat_res.scalars().all()
        assert len(messages) == 1
        assert messages[0].content == "Welcome to the lifecycle test."
