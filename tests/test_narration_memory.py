import pytest

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.chat import ChatMessage
from backend.models.session_state import SessionState
from backend.models.user import User

pytestmark = pytest.mark.asyncio


async def _seed_context(db, max_memory_turns_adv=30, max_memory_turns_state=None):
    user = User(username="testplayer", hashed_password="pw", role="user")
    adv = AdventureTemplate(
        id="adv-mem-1",
        title="Memory Adventure",
        owner_id="admin",
        time_per_turn=5,
        max_memory_turns=max_memory_turns_adv,
        strict_rules=False,
    )
    db.add_all([user, adv])
    await db.flush()

    avatar = Avatar(
        id="av-mem-1",
        template_id=adv.id,
        user_id=user.id,
        name="Hero",
        role="Mage",
        hp=100,
        stats={},
    )
    db.add(avatar)
    await db.flush()

    state = SessionState(
        session_id="session-mem-1",
        template_id=adv.id,
        avatar_id=avatar.id,
        user_id=user.id,
        current_scene_id="START",
        in_game_time=0,
        max_memory_turns=max_memory_turns_state
        if max_memory_turns_state is not None
        else max_memory_turns_adv,
    )
    db.add(state)
    await db.commit()
    return user, adv, avatar, state


async def test_build_narration_messages_default_30(setup_test_db):
    """Verifies that up to 30 past turns are included in narration messages."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, adv, avatar, state = await _seed_context(db, max_memory_turns_adv=30)
        manager = GameTurnManager(db, "session-mem-1", user)
        manager.state = state
        manager.adventure = adv
        manager.avatar = avatar

        # Seed 5 completed turns (user + assistant)
        for i in range(1, 6):
            db.add(ChatMessage(session_id="session-mem-1", role="user", content=f"User action {i}"))
            db.add(
                ChatMessage(
                    session_id="session-mem-1", role="assistant", content=f"Narrator response {i}"
                )
            )
        # Seed current turn user message
        db.add(ChatMessage(session_id="session-mem-1", role="user", content="Current user action"))
        await db.commit()

        messages, turns = await manager._build_narration_messages(
            "System instruction", "Current user action"
        )
        assert turns == 30
        assert messages[0] == {"role": "system", "content": "System instruction"}
        # Should include all 5 past turns (user + assistant) + current turn user action = 1 + 10 + 1 = 12
        assert len(messages) == 12
        assert messages[-1] == {"role": "user", "content": "Current user action"}
        assert messages[1] == {"role": "user", "content": "User action 1"}
        assert messages[2] == {"role": "assistant", "content": "Narrator response 1"}


async def test_build_narration_messages_default_10(setup_test_db):
    """Verifies that the default memory turns is now 10 when unset."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user = User(username="defaultplayer", hashed_password="pw", role="user")
        adv = AdventureTemplate(
            id="adv-default-10",
            title="Default 10 Adventure",
            owner_id="admin",
            time_per_turn=5,
            strict_rules=False,
        )
        db.add_all([user, adv])
        await db.flush()

        avatar = Avatar(
            id="av-default-10",
            template_id=adv.id,
            user_id=user.id,
            name="Hero",
            role="Mage",
            hp=100,
            stats={},
        )
        db.add(avatar)
        await db.flush()

        state = SessionState(
            session_id="session-default-10",
            template_id=adv.id,
            avatar_id=avatar.id,
            user_id=user.id,
            current_scene_id="START",
            in_game_time=0,
        )
        db.add(state)
        await db.commit()

        # Both model defaults should be 10
        assert adv.max_memory_turns == 10
        assert state.max_memory_turns == 10

        manager = GameTurnManager(db, "session-default-10", user)
        manager.state = state
        manager.adventure = adv
        manager.avatar = avatar

        messages, turns = await manager._build_narration_messages(
            "System instruction", "Current user action"
        )
        assert turns == 10


async def test_build_narration_messages_limits_to_configured_turns(setup_test_db):
    """Verifies that only the last N turns are included when max_memory_turns is set."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        # Configure session for only 2 memory turns
        user, adv, avatar, state = await _seed_context(
            db, max_memory_turns_adv=30, max_memory_turns_state=2
        )
        manager = GameTurnManager(db, "session-mem-1", user)
        manager.state = state
        manager.adventure = adv
        manager.avatar = avatar

        # Seed 5 completed turns
        for i in range(1, 6):
            db.add(ChatMessage(session_id="session-mem-1", role="user", content=f"User action {i}"))
            db.add(
                ChatMessage(
                    session_id="session-mem-1", role="assistant", content=f"Narrator response {i}"
                )
            )
        # Seed current turn user action
        db.add(ChatMessage(session_id="session-mem-1", role="user", content="Turn 6 action"))
        await db.commit()

        messages, turns = await manager._build_narration_messages("System prompt", "Turn 6 action")
        assert turns == 2
        # Should include:
        # 0: system
        # 1: Turn 4 user
        # 2: Turn 4 assistant
        # 3: Turn 5 user
        # 4: Turn 5 assistant
        # 5: Turn 6 user
        assert len(messages) == 6
        assert messages[0]["role"] == "system"
        assert messages[1] == {"role": "user", "content": "User action 4"}
        assert messages[2] == {"role": "assistant", "content": "Narrator response 4"}
        assert messages[3] == {"role": "user", "content": "User action 5"}
        assert messages[4] == {"role": "assistant", "content": "Narrator response 5"}
        assert messages[5] == {"role": "user", "content": "Turn 6 action"}


async def test_build_narration_messages_zero_memory(setup_test_db):
    """Verifies that setting max_memory_turns=0 yields only system prompt and current action."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, adv, avatar, state = await _seed_context(
            db, max_memory_turns_adv=30, max_memory_turns_state=0
        )
        manager = GameTurnManager(db, "session-mem-1", user)
        manager.state = state
        manager.adventure = adv
        manager.avatar = avatar

        # Seed 3 completed turns
        for i in range(1, 4):
            db.add(ChatMessage(session_id="session-mem-1", role="user", content=f"Action {i}"))
            db.add(
                ChatMessage(session_id="session-mem-1", role="assistant", content=f"Response {i}")
            )
        db.add(ChatMessage(session_id="session-mem-1", role="user", content="Latest action"))
        await db.commit()

        messages, turns = await manager._build_narration_messages("Sys", "Latest action")
        assert turns == 0
        assert len(messages) == 2
        assert messages[0] == {"role": "system", "content": "Sys"}
        assert messages[1] == {"role": "user", "content": "Latest action"}


async def test_build_narration_messages_system_events_merged_cleanly(setup_test_db):
    """Current-turn system events are merged into the user turn; past-turn events are dropped.

    Past events were already narrated, so repeating them only costs tokens.
    """
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, adv, avatar, state = await _seed_context(db, max_memory_turns_state=5)
        manager = GameTurnManager(db, "session-mem-1", user)
        manager.state = state
        manager.adventure = adv
        manager.avatar = avatar

        # Turn 1 with a system roll
        db.add(ChatMessage(session_id="session-mem-1", role="user", content="I kick the door"))
        db.add(
            ChatMessage(
                session_id="session-mem-1",
                role="system",
                content="Strength DC 15: Rolled 12 (Fail)",
            )
        )
        db.add(
            ChatMessage(
                session_id="session-mem-1",
                role="assistant",
                content="The door rattles but stays shut.",
            )
        )

        # Turn 2 with a system roll before narration
        db.add(ChatMessage(session_id="session-mem-1", role="user", content="I pick the lock"))
        db.add(
            ChatMessage(
                session_id="session-mem-1",
                role="system",
                content="Agility DC 10: Rolled 18 (Success)",
            )
        )
        await db.commit()

        messages, turns = await manager._build_narration_messages("Sys", "I pick the lock")
        assert len(messages) == 4
        # Check that no non-first message has role == "system" (crucial for Anthropic API compatibility)
        for m in messages[1:]:
            assert m["role"] in {"user", "assistant"}

        assert messages[1] == {"role": "user", "content": "I kick the door"}
        assert messages[2] == {"role": "assistant", "content": "The door rattles but stays shut."}
        assert "Agility DC 10: Rolled 18 (Success)" in messages[3]["content"]
        assert messages[-1]["role"] == "user"


async def test_build_narration_messages_prepends_turn_context_and_skips_debug(setup_test_db):
    """Per-turn context goes into the final user message; debug lines never reach the LLM."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, adv, avatar, state = await _seed_context(db, max_memory_turns_state=5)
        manager = GameTurnManager(db, "session-mem-1", user)
        manager.state = state
        manager.adventure = adv
        manager.avatar = avatar

        db.add(ChatMessage(session_id="session-mem-1", role="user", content="I open the chest"))
        db.add(
            ChatMessage(
                session_id="session-mem-1", role="system", content="[DEBUG LOG] Turn completed"
            )
        )
        db.add(
            ChatMessage(
                session_id="session-mem-1", role="system", content="Added Gold to your inventory."
            )
        )
        await db.commit()

        messages, _ = await manager._build_narration_messages(
            "Static system prompt",
            "I open the chest",
            turn_context="CURRENT STATE:\nTURN RESOLUTION:",
        )

        # Assert
        assert messages[0] == {"role": "system", "content": "Static system prompt"}
        final = messages[-1]["content"]
        assert final.startswith("CURRENT STATE:")
        assert "PLAYER ACTION:\nI open the chest" in final
        assert "[Game Event: Added Gold to your inventory.]" in final
        assert "[DEBUG LOG]" not in final


async def test_build_narration_messages_marks_current_turn_script_lines(setup_test_db):
    """A scripted NPC line from this turn is an annotation, not a finished GM reply.

    Replayed as an assistant turn, the model answered the player action a second time
    and let the NPC repeat the scripted clue in other words.
    """
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        # Arrange
        user, adv, avatar, state = await _seed_context(db, max_memory_turns_state=5)
        manager = GameTurnManager(db, "session-mem-1", user)
        manager.state = state
        manager.adventure = adv
        manager.avatar = avatar
        db.add(ChatMessage(session_id="session-mem-1", role="user", content="I wave at Dad"))
        db.add(ChatMessage(session_id="session-mem-1", role="assistant", content="Dad waves back."))
        db.add(ChatMessage(session_id="session-mem-1", role="user", content="calm down, I got you"))
        db.add(
            ChatMessage(
                session_id="session-mem-1",
                role="assistant",
                content='Dad: "The locker code is on my poster!"',
            )
        )
        await db.commit()

        # Act
        messages, _ = await manager._build_narration_messages(
            "Sys", "calm down, I got you", turn_context="TURN RESOLUTION:"
        )

        # Assert
        assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]
        assert messages[2] == {"role": "assistant", "content": "Dad waves back."}
        final = messages[-1]["content"]
        assert final.count("calm down, I got you") == 1
        assert (
            '[Already shown to the player this turn: Dad: "The locker code is on my poster!"]'
            in final
        )


async def test_narration_history_starts_at_the_current_scene(setup_test_db):
    """Turns played in a scene the player left are not replayed: their NPCs must not speak."""
    from datetime import UTC, datetime, timedelta

    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, adv, avatar, state = await _seed_context(db)
        manager = GameTurnManager(db, "session-mem-1", user)
        manager.state, manager.adventure, manager.avatar = state, adv, avatar
        base = datetime(2030, 1, 1, tzinfo=UTC)
        rows = [
            ("user", "Talk to Vera", "HALL"),
            ("assistant", 'Vera: "Welcome to the lab."', "HALL"),
            ("user", "Go to the lab", "HALL"),
            ("assistant", "You walk into the lab.", "START"),
            ("user", "Look at the fridge", "START"),
            ("assistant", "The fridge hums.", "START"),
            ("user", "Open the fridge", "START"),
        ]
        for i, (role, content, scene) in enumerate(rows):
            db.add(
                ChatMessage(
                    session_id="session-mem-1",
                    role=role,
                    content=content,
                    scene_id=scene,
                    created_at=base + timedelta(seconds=i),
                )
            )
        await db.commit()

        messages, _turns = await manager._build_narration_messages("System", "Open the fridge")

    replayed = [m["content"] for m in messages[1:]]
    assert replayed == [
        "Go to the lab",
        "You walk into the lab.",
        "Look at the fridge",
        "The fridge hums.",
        "Open the fridge",
    ]
    assert not any("Vera" in content for content in replayed)
