"""Each session has its own world map, showing scenes with the session's own scene images."""

import pytest

from backend.api.routes.adventures import chat_snapshot
from backend.api.routes.adventures.chat_snapshot import build_session_map
from backend.api.routes.adventures.logic import AdventureLogic
from backend.models.world_entity import WorldScene
from tests.conftest import TestSessionLocal
from tests.test_game_loop import _seed_game_context

STORED_IMAGE = "/data/adventures/sessions/session-1/visuals/scenes/placeholder.png"
SESSION_IMAGE = "/data/adventures/sessions/session-1/visuals/scenes/hall.jpg"


@pytest.fixture(autouse=True)
def _keep_urls(monkeypatch):
    monkeypatch.setattr(
        chat_snapshot.AdventureLogic,
        "resolve_existing_data_asset_url",
        staticmethod(lambda url: url),
    )


@pytest.mark.asyncio
async def test_session_map_ignores_template_and_other_session_maps():
    async with TestSessionLocal() as db:
        # Arrange: the shared template map and another session's map both know a scene.
        _user, adv, _avatar, state = await _seed_game_context(db)
        template_map = await AdventureLogic.get_or_create_map(db, adv.id)
        template_map.nodes = {"VAULT": {"id": "VAULT", "label": "Vault"}}
        other_map = await AdventureLogic.get_or_create_map(db, adv.id, session_id="other-session")
        other_map.nodes = {"TOWER": {"id": "TOWER", "label": "Tower"}}
        await db.commit()

        # Act
        map_dict = await build_session_map(db, state)

        # Assert
        assert "VAULT" not in map_dict["nodes"]
        assert "TOWER" not in map_dict["nodes"]


@pytest.mark.asyncio
async def test_map_node_uses_current_session_scene_image():
    async with TestSessionLocal() as db:
        # Arrange: the node still holds the image from the first visit (a placeholder).
        _user, adv, _avatar, state = await _seed_game_context(db)
        world_map = await AdventureLogic.get_or_create_map(db, adv.id, session_id=state.session_id)
        world_map.nodes = {
            "START": {"id": "START", "label": "Start", "image_url": STORED_IMAGE},
            "VAULT": {"id": "VAULT", "label": "Vault", "image_url": STORED_IMAGE},
        }
        db.add(
            WorldScene(
                id="START",
                template_id=adv.id,
                session_id=state.session_id,
                label="Start",
                description="The beginning.",
                image_url=SESSION_IMAGE,
            )
        )
        await db.commit()

        # Act
        map_dict = await build_session_map(db, state)

        # Assert: the session scene's image wins; nodes without a session scene keep theirs.
        assert map_dict["nodes"]["START"]["image_url"] == SESSION_IMAGE
        assert map_dict["nodes"]["VAULT"]["image_url"] == STORED_IMAGE
