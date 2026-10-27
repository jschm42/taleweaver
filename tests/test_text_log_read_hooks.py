"""Read hooks (on_read_script / on_read_text) of a readable fire on the first read only."""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldScene
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio

GAME_ID = "read-hooks-session"
TEMPLATE_ID = "read-hooks-template"


async def _seed() -> None:
    async with TestSessionLocal() as db:
        user = (await db.execute(select(User).limit(1))).scalars().first()
        db.add(AdventureTemplate(id=TEMPLATE_ID, owner_id=user.id, title="Diner", is_ready=True))
        db.add(
            Avatar(id="read-hooks-avatar", template_id=TEMPLATE_ID, user_id=user.id, name="Jack")
        )
        await db.flush()
        db.add(
            GameSession(
                id=GAME_ID,
                user_id=user.id,
                avatar_id="read-hooks-avatar",
                template_id=TEMPLATE_ID,
                adventure_title="Diner",
                status="active",
            )
        )
        await db.flush()
        db.add_all(
            [
                SessionState(
                    session_id=GAME_ID,
                    user_id=user.id,
                    template_id=TEMPLATE_ID,
                    avatar_id="read-hooks-avatar",
                    current_scene_id="CORNER_BOOTH",
                ),
                WorldScene(
                    id="CORNER_BOOTH", template_id=TEMPLATE_ID, label="Booth", description="Dim."
                ),
                WorldEntity(
                    id="SLANG_MEMO",
                    template_id=TEMPLATE_ID,
                    entity_type="OBJECT",
                    item_type="READABLE",
                    name="Lingo Memo",
                    description="Onionskin paper.",
                    current_scene_id="CORNER_BOOTH",
                    metadata_json={
                        "on_read_script": "tw.vars.set('read_slang_memo', True)",
                        "on_read_text": "You pocket the lingo translation.",
                    },
                ),
            ]
        )
        await db.commit()


async def test_reopening_a_text_log_does_not_repeat_read_hooks(
    auth_client, setup_test_db, monkeypatch
):
    # Arrange
    await _seed()
    trigger = AsyncMock()
    monkeypatch.setattr(
        "backend.api.routes.adventures.gameplay.TriggerService.execute_trigger", trigger
    )
    url = f"/api/adventures/{GAME_ID}/text-logs/SLANG_MEMO/read"

    # Act
    first = await auth_client.post(url)
    second = await auth_client.post(url)

    # Assert
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["is_read"] is True
    assert trigger.await_count == 1
