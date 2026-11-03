"""Scripts reward the protagonist: XP (tw.player.add_xp) and awards (tw.awards.grant)."""

import pytest
from sqlalchemy import select

from backend.engine.scripting.runner import ScriptRunner
from backend.models.chat import ChatMessage
from tests.conftest import TestSessionLocal
from tests.test_script_turn_integration import _build_test_turn_manager


def _run(ctx, code: str) -> None:
    ScriptRunner([]).execute_code(code, {"tw": ctx}, script_id="test")


@pytest.mark.asyncio
async def test_script_xp_is_added_to_the_protagonist(setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _build_test_turn_manager(db, [], session_id="sess_xp")
        manager.avatar.exp = 40
        ctx = await manager._build_script_context()
        _run(ctx, "tw.vars.set('before', tw.player.xp)\ntw.player.add_xp(25)")

        # Act
        messages = await manager._apply_script_changeset(ctx.changeset)

        # Assert
        assert ctx.changeset.var_updates["before"] == 40
        assert manager.avatar.exp == 65
        assert any("You gain 25 XP" in str(getattr(m, "content", m)) for m in messages)
        # Stored in the chat: a dialog choice reloads the chat from the database.
        await db.flush()
        stored = (
            (
                await db.execute(
                    select(ChatMessage.content).where(ChatMessage.session_id == "sess_xp")
                )
            )
            .scalars()
            .all()
        )
        assert "You gain 25 XP (Script)." in stored


@pytest.mark.asyncio
async def test_script_xp_never_goes_below_zero(setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _build_test_turn_manager(db, [], session_id="sess_xp_neg")
        manager.avatar.exp = 10
        ctx = await manager._build_script_context()
        _run(ctx, "tw.player.add_xp(-50)")

        # Act
        await manager._apply_script_changeset(ctx.changeset)

        # Assert
        assert manager.avatar.exp == 0


@pytest.mark.asyncio
async def test_script_award_is_earned_by_the_player(setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _build_test_turn_manager(db, [], session_id="sess_award")
        manager.adventure.awards = [
            {"key": "AWARD_BRASS_LEVER", "title": "Brass Lever Whisperer", "tier": "gold"}
        ]
        ctx = await manager._build_script_context()
        _run(ctx, "tw.awards.grant('award_brass_lever')")

        # Act
        messages = await manager._apply_script_changeset(ctx.changeset)

        # Assert
        earned = [a["key"] for a in manager.user.earned_awards or []]
        assert earned == ["AWARD_BRASS_LEVER"]
        assert any(
            "Award Achievement: Brass Lever Whisperer" in str(getattr(m, "content", m))
            for m in messages
        )
