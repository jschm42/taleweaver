import pytest
from sqlalchemy import select
from unittest.mock import AsyncMock, MagicMock

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.engine.rule_engine import GameEvent, WorldEntityUpdate, ExitUpdate
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene

pytestmark = pytest.mark.asyncio

async def _seed_game_context(db):
    user = User(username="player1", hashed_password="pw", role="user")
    adv = AdventureTemplate(
        id="adv-1",
        title="Test Adventure",
        owner_id="admin",
        time_per_turn=5,
        strict_rules=True
    )
    db.add_all([user, adv])
    await db.flush()

    avatar = Avatar(
        id="av-1",
        template_id=adv.id,
        user_id=user.id,
        name="Hero",
        role="Warrior",
        hp=100,
        stats={"strength": 10, "dexterity": 10},
        inventory=[]
    )
    db.add(avatar)
    await db.flush()

    state = SessionState(
        session_id="session-1",
        template_id=adv.id,
        avatar_id=avatar.id,
        user_id=user.id,
        current_scene_id="START",
        in_game_time=0
    )
    db.add(state)
    await db.commit()
    return user, adv, avatar, state

async def test_key_item_referenced_helper(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, adv, avatar, state = await _seed_game_context(db)
        
        # Add key item to DB
        key_item = WorldEntity(
            id="BOX_KEY",
            session_id=state.session_id,
            entity_type="OBJECT",
            name="Rusty Box Key",
            description="A rusty key.",
            current_scene_id="START"
        )
        # Add screwdriver item to DB
        screwdriver = WorldEntity(
            id="SCREWDRIVER",
            session_id=state.session_id,
            entity_type="OBJECT",
            name="Screwdriver",
            description="A simple screwdriver.",
            current_scene_id="START"
        )
        db.add_all([key_item, screwdriver])
        await db.commit()

        manager = GameTurnManager(db, state.session_id, user)
        await manager.initialize()

        # 1. Direct ID match
        assert await manager._is_key_item_referenced("BOX_KEY", "i use box_key on chest") is True

        # 2. Direct name match
        assert await manager._is_key_item_referenced("BOX_KEY", "use rusty box key") is True

        # 3. Token match
        assert await manager._is_key_item_referenced("BOX_KEY", "use key on chest") is True

        # 4. Token boundary check (no partial match)
        assert await manager._is_key_item_referenced("BOX_KEY", "donkey eats banana") is False

        # 5. German translation fallback for key
        assert await manager._is_key_item_referenced("BOX_KEY", "öffne mit schlüssel") is True

        # 6. Not mentioned
        assert await manager._is_key_item_referenced("BOX_KEY", "open the chest please") is False

        # 7. German translation/synonym fallback for screwdriver
        assert await manager._is_key_item_referenced("SCREWDRIVER", "benutze schraubenzieher") is True
        assert await manager._is_key_item_referenced("SCREWDRIVER", "benutze schraubendreher") is True

async def test_container_unlock_blocked_without_mention(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, adv, avatar, state = await _seed_game_context(db)

        # Give key item in inventory
        avatar.inventory = [{"id": "BOX_KEY", "name": "Box Key"}]
        db.add(avatar)
        await db.commit()
        
        # Add locked container
        container = WorldEntity(
            id="STRANGE_BOX",
            session_id=state.session_id,
            entity_type="OBJECT",
            name="Strange Box",
            description="A strange box.",
            item_type="CONTAINER",
            metadata_json={"code_to_unlock": "", "item_to_unlock": "BOX_KEY", "locked": True},
            current_scene_id="START"
        )
        db.add(container)
        await db.commit()

        manager = GameTurnManager(db, state.session_id, user)
        await manager.initialize()

        print("DEBUG INVENTORY IDS:", [i.get("id") for i in (manager.avatar.inventory or [])])

        # CASE 1: Player tries to unlock but does not mention the key
        event1 = GameEvent(
            updated_entities=[WorldEntityUpdate(entity_id="STRANGE_BOX", locked=False)]
        )
        reasons1 = await manager._enforce_container_unlock_guardrails(event1, "open strange box")
        print("DEBUG REASONS1:", reasons1)
        assert reasons1
        assert "specify which item you are using" in reasons1[0]
        # Guardrail should revert event to locked=True
        assert any(up.entity_id == "STRANGE_BOX" and up.locked is True for up in event1.updated_entities)

        # CASE 2: Player mentions key name
        event2 = GameEvent(
            updated_entities=[WorldEntityUpdate(entity_id="STRANGE_BOX", locked=False)]
        )
        reasons2 = await manager._enforce_container_unlock_guardrails(event2, "open strange box with key")
        print("DEBUG REASONS2:", reasons2)
        assert not reasons2
        # Event should keep locked=False
        assert any(up.entity_id == "STRANGE_BOX" and up.locked is False for up in event2.updated_entities)

async def test_exit_unlock_blocked_without_mention(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, adv, avatar, state = await _seed_game_context(db)

        # Give key in inventory
        avatar.inventory = [{"id": "EXIT_KEY", "name": "Exit Key"}]
        db.add(avatar)
        await db.commit()

        # Set up current scene and exit
        db.add(WorldScene(id="START", session_id=state.session_id, label="Start Scene", description="start scene description"))
        db.add(WorldScene(id="CELLAR", session_id=state.session_id, label="Cellar", description="cellar scene description"))
        db.add(WorldExit(
            session_id=state.session_id,
            from_scene_id="START",
            to_scene_id="CELLAR",
            label="Heavy Oak Door",
            is_locked=True,
            item_to_unlock="EXIT_KEY"
        ))
        await db.commit()

        manager = GameTurnManager(db, state.session_id, user)
        await manager.initialize()

        # CASE 1: Player tries to unlock exit but doesn't mention key
        event1 = GameEvent(
            new_scene_id="CELLAR",
            updated_exits=[ExitUpdate(from_scene_id="START", to_scene_id="CELLAR", is_locked=False)]
        )
        reasons1 = await manager._enforce_exit_unlock_guardrails(event1, "go through the heavy oak door")
        assert reasons1
        assert "specify which item you are using" in reasons1[0]
        assert event1.new_scene_id is None
        assert any(up.is_locked is True for up in event1.updated_exits)

        # CASE 2: Player mentions key
        event2 = GameEvent(
            new_scene_id="CELLAR",
            updated_exits=[ExitUpdate(from_scene_id="START", to_scene_id="CELLAR", is_locked=False)]
        )
        reasons2 = await manager._enforce_exit_unlock_guardrails(event2, "use exit key to unlock oak door and enter cellar")
        assert not reasons2
        assert event2.new_scene_id == "CELLAR"
        assert any(up.is_locked is False for up in event2.updated_exits)

async def test_switch_transition_blocked_without_mention(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, adv, avatar, state = await _seed_game_context(db)

        # Give item
        avatar.inventory = [{"id": "SCREWDRIVER", "name": "Screwdriver"}]
        db.add(avatar)
        await db.commit()

        # Add switch entity
        switch = WorldEntity(
            id="POWER_BOX",
            session_id=state.session_id,
            entity_type="OBJECT",
            name="Power Box Switch",
            description="A power box switch.",
            item_type="SWITCH",
            current_scene_id="START",
            metadata_json={
                "switch": {
                    "states": ["OFF", "ON"],
                    "initial_state": "OFF",
                    "transitions": [
                        {
                            "from": "OFF",
                            "to": "ON",
                            "gates": {
                                "item": "SCREWDRIVER"
                            }
                        }
                    ]
                }
            }
        )
        db.add(switch)
        await db.commit()

        manager = GameTurnManager(db, state.session_id, user)
        await manager.initialize()

        # CASE 1: Player turns switch but does not mention screwdriver
        event1 = GameEvent(
            updated_entities=[WorldEntityUpdate(entity_id="POWER_BOX", switch_state="ON")]
        )
        reasons1 = await manager._enforce_switch_transition_guardrails(event1, "flip power box switch")
        assert reasons1
        assert "specify which item you are using" in reasons1[0]
        assert any(up.entity_id == "POWER_BOX" and up.switch_state == "OFF" for up in event1.updated_entities)

        # CASE 2: Player mentions screwdriver
        event2 = GameEvent(
            updated_entities=[WorldEntityUpdate(entity_id="POWER_BOX", switch_state="ON")]
        )
        reasons2 = await manager._enforce_switch_transition_guardrails(event2, "use screwdriver on power box")
        assert not reasons2
        assert any(up.entity_id == "POWER_BOX" and up.switch_state == "ON" for up in event2.updated_entities)

async def test_rule_violations_modify_narrative_description(setup_test_db, monkeypatch):
    """Verifies that rule violations override narrative_description in game_event for narration model."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, adv, avatar, state = await _seed_game_context(db)
        avatar.inventory = [{"id": "BOX_KEY", "name": "Box Key"}]
        db.add(avatar)
        await db.commit()

        # Mock LLM Pass 1 to try to open the box without key mention
        # We also mock Pass 2 to intercept narration_prompt sent to stream_simple_task
        mock_llm_instance = MagicMock()
        mock_event = GameEvent(
            narrative_description="The hero successfully unlocks the strange box and finds loot.",
            updated_entities=[WorldEntityUpdate(entity_id="STRANGE_BOX", locked=False)]
        )
        mock_llm_instance.aexecute_complex_task = AsyncMock(return_value=mock_event)

        # Capture the prompt passed to stream_simple_task
        captured_prompts = []
        async def mock_stream(system_prompt, user_prompt, model_name):
            captured_prompts.append(system_prompt)
            # Yield empty/dummy chunk
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="The box remains locked."))])

        mock_llm_instance.stream_simple_task = AsyncMock(side_effect=mock_stream)
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)

        # Seed locked box
        container = WorldEntity(
            id="STRANGE_BOX",
            session_id=state.session_id,
            entity_type="OBJECT",
            name="Strange Box",
            description="A strange box.",
            item_type="CONTAINER",
            metadata_json={"code_to_unlock": "", "item_to_unlock": "BOX_KEY", "locked": True},
            current_scene_id="START"
        )
        db.add(container)
        await db.commit()

        # Act
        manager = GameTurnManager(db, state.session_id, user)
        # Player says "open box" without referencing the key item
        async for _ in manager.process_turn("open box"):
            pass

        # Assert: rule violation occurred (no key mentioned)
        # Verify that captured system prompt does NOT contain the success narrative_description
        # and instead contains the failure warning
        assert len(captured_prompts) == 1
        narration_prompt = captured_prompts[0]
        
        # Verify the success narration was overwritten
        assert "The hero successfully unlocks the strange box" not in narration_prompt
        # Verify the failure warning is present
        assert "The attempted action failed and was reverted due to the following rule violations" in narration_prompt
        assert "You must specify which item you are using to unlock Strange Box" in narration_prompt

async def test_resolve_session_exit_prefers_session_scoped(setup_test_db):
    """Verifies that _resolve_session_exit prefers the session-scoped exit over the template-scoped exit."""
    from tests.conftest import TestSessionLocal
    from backend.api.routes.adventures.gameplay import _resolve_session_exit

    async with TestSessionLocal() as db:
        user, adv, avatar, state = await _seed_game_context(db)

        # 1. Create a template-scoped exit (locked)
        template_exit = WorldExit(
            id="CELLAR_EXIT_TEMPLATE",
            template_id=adv.id,
            session_id=None,
            from_scene_id="START",
            to_scene_id="CELLAR",
            label="Heavy Oak Door",
            is_locked=True
        )
        db.add(template_exit)

        # 2. Create a session-scoped exit (unlocked)
        session_exit = WorldExit(
            id="CELLAR_EXIT_SESSION",
            template_id=adv.id,
            session_id=state.session_id,
            from_scene_id="START",
            to_scene_id="CELLAR",
            label="Heavy Oak Door",
            is_locked=False
        )
        db.add(session_exit)
        await db.commit()

        # Act: resolve exit by querying with the template exit ID
        resolved = await _resolve_session_exit(db, state, "CELLAR_EXIT_TEMPLATE")

        # Assert: should map to and return the session-scoped exit (unlocked)
        assert resolved is not None
        assert resolved.id == "CELLAR_EXIT_SESSION"
        assert resolved.session_id == state.session_id
        assert resolved.is_locked is False

