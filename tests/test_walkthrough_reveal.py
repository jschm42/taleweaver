import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.api.routes.adventures.gameplay import _parse_walkthrough_steps
from backend.api.routes.adventures.gameplay_logic import GameTurnManager, WALKTHROUGH_REVEAL_COST
from backend.core.auth import get_password_hash
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.user import User

def test_parse_walkthrough_steps_numbered():
    raw = (
        "1. Examine the room and search the desk.\n"
        "2. Take the brass key and unlock door.\n"
        "3. Escape the dungeon."
    )
    steps = _parse_walkthrough_steps(raw)
    assert len(steps) == 3
    assert steps[0]["title"] == "Examine the room and search the desk."


def test_parse_walkthrough_steps_paragraphs():
    raw = "First part of walkthrough.\n\nSecond part of walkthrough."
    steps = _parse_walkthrough_steps(raw)
    assert len(steps) == 2
    assert steps[0]["title"] == "Step 1"
    assert steps[0]["content"] == "First part of walkthrough."
    assert steps[1]["title"] == "Step 2"
    assert steps[1]["content"] == "Second part of walkthrough."


@pytest.mark.asyncio
async def test_walkthrough_reveal_deducts_150_xp_and_grants_negative_award(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user = User(
            username="walkthrough-player",
            hashed_password=get_password_hash("pw"),
            role="user",
            earned_awards=[],
        )
        adv = AdventureTemplate(
            id="adv-walkthrough",
            title="Walkthrough Adventure",
            owner_id="owner",
            walkthrough="1. Enter temple\n2. Solve puzzle",
            awards=[{"key": "GOLD_EXPLORER", "title": "Gold Explorer", "tier": "gold", "description": "Found gold"}],
        )
        db.add_all([user, adv])
        await db.flush()

        avatar = Avatar(
            id="av-walkthrough",
            template_id=adv.id,
            user_id=user.id,
            name="Hero",
            exp=200,
        )
        session = GameSession(
            id="session-walkthrough",
            user_id=user.id,
            avatar_id=avatar.id,
            template_id=adv.id,
            adventure_title=adv.title,
        )
        state = SessionState(
            session_id=session.id,
            template_id=adv.id,
            avatar_id=avatar.id,
            user_id=user.id,
            walkthrough=adv.walkthrough,
            is_walkthrough_revealed=False,
            current_scene_id="SCENE_1",
        )
        db.add_all([avatar, session, state])
        await db.commit()

        manager = GameTurnManager(db, session.id, user)
        assert await manager.initialize()

        # Trigger walkthrough reveal via process_turn
        chunks = []
        async for chunk in manager.process_turn("/walkthrough reveal"):
            chunks.append(chunk)

        combined = "".join(chunks)
        assert "Walkthrough freigeschaltet" in combined
        assert "-150 XP" in combined
        assert manager.state.is_walkthrough_revealed is True
        # Avatar XP was 200, should now be 50 (200 - 150)
        assert manager.avatar.exp == 50

        # Check negative award was granted
        awards = user.earned_awards or []
        assert any(aw.get("key") == "SPOILER_SEEKER" and aw.get("tier") == "negative" for aw in awards)

        # Check _build_awards_payload includes the negative award as earned
        payload_awards = await manager.state_applier._build_awards_payload(adv)
        spoiler_award = next((aw for aw in payload_awards if aw.get("key") == "SPOILER_SEEKER"), None)
        assert spoiler_award is not None
        assert spoiler_award.get("tier") == "negative"
        assert spoiler_award.get("is_earned") is True
