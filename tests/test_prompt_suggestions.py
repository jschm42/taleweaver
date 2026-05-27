from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.core.auth import get_password_hash
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene

pytestmark = pytest.mark.asyncio


async def _seed_prompt_context(db):
    user = User(
        username="suggest-player",
        hashed_password=get_password_hash("pw"),
        role="user",
        llm_settings={
            "small_model": "gpt-4o-mini",
            "small_model_provider": "openai",
            "preferred_provider": "openai",
        },
    )
    adv = AdventureTemplate(id="adv-suggest", title="Suggestion Adventure", owner_id="owner")
    db.add_all([user, adv])
    await db.flush()

    avatar = Avatar(
        id="av-suggest",
        template_id=adv.id,
        user_id=user.id,
        name="Hero",
        inventory=[{"id": "ROPE", "name": "Rope", "item_type": "TOOL"}],
    )
    state = SessionState(
        session_id="session-suggest",
        template_id=adv.id,
        avatar_id=avatar.id,
        user_id=user.id,
        current_scene_id="START",
    )
    db.add_all([avatar, state])
    db.add_all(
        [
            WorldScene(
                id="START",
                session_id=state.session_id,
                template_id=adv.id,
                label="Dusty Hall",
                description="A dimly lit hall with old stone floors.",
            ),
            WorldEntity(
                id="GUIDE_NPC",
                session_id=state.session_id,
                template_id=adv.id,
                entity_type="NPC",
                name="Guide Rowan",
                description="A calm guide.",
                current_scene_id="START",
                is_hidden=False,
            ),
            WorldEntity(
                id="HIDDEN_NPC",
                session_id=state.session_id,
                template_id=adv.id,
                entity_type="NPC",
                name="Hidden Watcher",
                description="Not discovered yet.",
                current_scene_id="START",
                is_hidden=True,
            ),
            WorldEntity(
                id="VISIBLE_OBJECT",
                session_id=state.session_id,
                template_id=adv.id,
                entity_type="OBJECT",
                name="Lantern",
                description="A brass lantern.",
                current_scene_id="START",
                is_hidden=False,
                is_in_inventory=False,
            ),
            WorldEntity(
                id="HIDDEN_OBJECT",
                session_id=state.session_id,
                template_id=adv.id,
                entity_type="OBJECT",
                name="Secret Lever",
                description="Concealed in the wall.",
                current_scene_id="START",
                is_hidden=True,
                is_in_inventory=False,
            ),
            WorldExit(
                id="exit-open",
                session_id=state.session_id,
                template_id=adv.id,
                from_scene_id="START",
                to_scene_id="COURTYARD",
                label="Courtyard Arch",
                is_locked=False,
            ),
            WorldExit(
                id="exit-locked",
                session_id=state.session_id,
                template_id=adv.id,
                from_scene_id="START",
                to_scene_id="VAULT",
                label="Vault Door",
                is_locked=True,
            ),
        ]
    )
    await db.commit()
    return user


async def test_player_only_context_filters_hidden_and_locked(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user = await _seed_prompt_context(db)
        manager = GameTurnManager(db, "session-suggest", user)
        assert await manager.initialize()

        context = await manager._build_player_only_suggestion_context()

        assert context["visible_npcs"] == ["Guide Rowan"]
        assert context["visible_objects"] == ["Lantern"]
        assert context["unlocked_exits"] == ["Courtyard Arch"]
        assert context["inventory_items"] == ["Rope"]


async def test_generate_prompt_suggestions_returns_and_persists_three_items(setup_test_db, monkeypatch):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user = await _seed_prompt_context(db)
        manager = GameTurnManager(db, "session-suggest", user)
        assert await manager.initialize()

        llm_mock = MagicMock()
        llm_mock.aexecute_simple_task = AsyncMock(
            return_value='["Examine floor scratches now", "Ask Guide Rowan quietly", "Wait and steady breathing"]'
        )
        monkeypatch.setattr(
            "backend.api.routes.adventures.gameplay_logic.GameMasterLLM",
            lambda *args, **kwargs: llm_mock,
        )

        suggestions = await manager._generate_prompt_suggestions("You hear a faint scrape in the hall.")

        assert len(suggestions) == 3
        assert all(len(text.split()) <= 6 for text in suggestions)
        saved = manager.extract_prompt_suggestions(manager.state.exit_states or {})
        assert saved == suggestions
