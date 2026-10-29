import pytest

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.session_state import SessionState
from backend.models.user import User
from tests.conftest import TestSessionLocal


async def _build_test_turn_manager(
    db_session, scripts: list[dict], session_id: str = "session_script_test"
) -> GameTurnManager:
    user = User(
        id=f"user_{session_id}",
        username=f"tester_{session_id}",
        hashed_password="fake",
        role="user",
    )
    db_session.add(user)
    await db_session.flush()

    adv = AdventureTemplate(
        id=f"adv_{session_id}",
        title="Scripted Adventure",
        owner_id=user.id,
        is_ready=True,
        rule_enforcement_mode="rpg",
        scripts_generation_enabled=True,
        original_manifest={"title": "Scripted Adventure", "scripts": scripts},
    )
    db_session.add(adv)
    await db_session.flush()

    avatar = Avatar(
        id=f"avatar_{session_id}",
        user_id=user.id,
        template_id=adv.id,
        name="Tester",
        hp=100,
        mana=50,
        stamina=50,
        inventory=[],
        status_effects=[],
    )
    db_session.add(avatar)
    await db_session.flush()

    state = SessionState(
        id=f"state_{session_id}",
        session_id=session_id,
        user_id=user.id,
        template_id=adv.id,
        avatar_id=avatar.id,
        current_scene_id="SCENE_START",
        entity_states={"LEVER_GATE": {"id": "LEVER_GATE", "switch_state": "OFF"}},
        exit_states={"SCENE_START:SCENE_SECRET": {"is_locked": True}},
        quests=[],
    )
    db_session.add(state)
    await db_session.commit()

    manager = GameTurnManager(db=db_session, user=user, game_id=session_id)
    manager.adventure = adv
    manager.avatar = avatar
    manager.state = state
    return manager


@pytest.mark.asyncio
async def test_script_triggers_in_turn_manager(setup_test_db):
    scripts = [
        {
            "id": "SCRIPT_START",
            "trigger": "on_turn_start",
            "code": """
turns = tw.vars.get("turn_counter", 0)
tw.vars.set("turn_counter", turns + 1)
tw.story.narrate("A cold draft blows through the corridor.")
""",
        },
        {
            "id": "SCRIPT_TRAP",
            "trigger": "on_enter_scene",
            "target_id": "SCENE_TRAP",
            "code": """
tw.player.modify_hp(-10)
tw.story.narrate("Spikes spring from the walls!")
""",
        },
        {
            "id": "SCRIPT_LEVER",
            "trigger": "on_interact",
            "target_id": "LEVER_GATE",
            "code": """
tw.exits.unlock("SCENE_START", "SCENE_SECRET")
tw.story.narrate("You hear gears grinding as the passage unlocks!")
""",
        },
    ]
    async with TestSessionLocal() as db_session:
        manager = await _build_test_turn_manager(db_session, scripts, "sess_triggers_test")
        runner = manager._get_script_runner()
        assert len(runner.scripts) == 3

        # Test 1: on_turn_start execution
        ctx = await manager._build_script_context()
        cs = runner.run_trigger("on_turn_start", ctx)
        assert cs.var_updates.get("turn_counter") == 1
        assert "A cold draft blows through the corridor." in cs.narrative_messages
        assert cs.has_changes is True

        await manager._apply_script_changeset(cs)
        assert manager.state.entity_states["__script_vars__"]["turn_counter"] == 1

        # Test 2: on_enter_scene execution
        ctx2 = await manager._build_script_context()
        cs_trap = runner.run_trigger("on_enter_scene", ctx2, target_id="SCENE_TRAP")
        assert cs_trap.player_hp_change == -10
        assert "Spikes spring from the walls!" in cs_trap.narrative_messages

        await manager._apply_script_changeset(cs_trap)
        assert manager.avatar.hp == 90

        # Test 3: on_interact execution
        ctx3 = await manager._build_script_context()
        cs_lever = runner.run_trigger("on_interact", ctx3, target_id="LEVER_GATE")
        assert any(
            e["from_scene_id"] == "SCENE_START"
            and e["to_scene_id"] == "SCENE_SECRET"
            and not e["is_locked"]
            for e in cs_lever.exit_updates
        )

        await manager._apply_script_changeset(cs_lever)
        assert manager.state.exit_states["SCENE_START:SCENE_SECRET"]["is_locked"] is False


@pytest.mark.asyncio
async def test_logic_and_narration_done_triggers(setup_test_db):
    scripts = [
        {
            "id": "SCRIPT_LOGIC_DONE",
            "trigger": "on_logic_pass_done",
            "code": """
tw.vars.set("logic_pass_completed", True)
tw.player.modify_stamina(10)
tw.story.narrate("The tactical situation stabilizes.")
""",
        },
        {
            "id": "SCRIPT_NARRATION_DONE",
            "trigger": "on_narration_done",
            "code": """
tw.vars.set("narration_completed", True)
tw.story.narrate("The echo of the tale lingers.")
""",
        },
    ]
    async with TestSessionLocal() as db_session:
        manager = await _build_test_turn_manager(db_session, scripts, "sess_passes_test")
        runner = manager._get_script_runner()
        assert len(runner.scripts) == 2

        # 1. on_logic_pass_done
        ctx1 = await manager._build_script_context()
        cs_logic = runner.run_trigger("on_logic_pass_done", ctx1)
        assert cs_logic.has_changes is True
        assert cs_logic.var_updates.get("logic_pass_completed") is True
        assert cs_logic.player_stamina_change == 10
        assert "The tactical situation stabilizes." in cs_logic.narrative_messages

        await manager._apply_script_changeset(cs_logic)
        assert manager.avatar.stamina == 60
        assert manager.state.entity_states["__script_vars__"]["logic_pass_completed"] is True

        # 2. on_narration_done
        ctx2 = await manager._build_script_context()
        cs_narr = runner.run_trigger("on_narration_done", ctx2)
        assert cs_narr.has_changes is True
        assert cs_narr.var_updates.get("narration_completed") is True
        assert "The echo of the tale lingers." in cs_narr.narrative_messages

        await manager._apply_script_changeset(cs_narr)
        assert manager.state.entity_states["__script_vars__"]["narration_completed"] is True


@pytest.mark.asyncio
async def test_adventure_template_scripts_property(setup_test_db):
    async with TestSessionLocal() as db_session:
        adv = AdventureTemplate(
            id="adv_scripts_prop_test",
            title="Scripts Property Test",
            owner_id="test_owner",
            is_ready=True,
            original_manifest={"title": "Manifest", "scripts": []},
        )
        db_session.add(adv)
        await db_session.flush()

        assert adv.scripts == []

        # Update scripts property
        new_scripts = [
            {
                "id": "SCRIPT_1",
                "name": "First Script",
                "trigger": "on_turn_start",
                "code": "tw.story.narrate('Hello')",
                "priority": 100,
                "is_active": True,
            }
        ]
        adv.scripts = new_scripts
        await db_session.commit()
        await db_session.refresh(adv)

        assert len(adv.scripts) == 1
        assert adv.scripts[0]["id"] == "SCRIPT_1"
        assert adv.original_manifest["scripts"][0]["name"] == "First Script"


@pytest.mark.asyncio
async def test_inline_pickup_and_proxy_helpers(setup_test_db):
    async with TestSessionLocal() as db_session:
        user = User(
            id="user_pickup_test",
            username="pickup_tester",
            hashed_password="fake",
            role="user",
        )
        db_session.add(user)
        await db_session.flush()

        adv = AdventureTemplate(
            id="adv_pickup_test",
            title="Pickup Script Test",
            owner_id=user.id,
            is_ready=True,
            original_manifest={"title": "Manifest", "scripts": []},
        )
        db_session.add(adv)

        avatar = Avatar(
            id="avatar_pickup_test",
            name="Arthur",
            user_id=user.id,
            hp=100,
            mana=50,
            stamina=100,
            inventory=[],
        )
        db_session.add(avatar)

        state = SessionState(
            id="state_pickup_test",
            session_id="session_pickup_test",
            user_id=user.id,
            template_id=adv.id,
            avatar_id=avatar.id,
            current_scene_id="LAB",
            entity_states={},
            exit_states={},
        )
        db_session.add(state)
        await db_session.flush()

        manager = GameTurnManager(db=db_session, user=user, game_id="session_pickup_test")
        manager.adventure = adv
        manager.avatar = avatar
        manager.state = state

        # Test script using show_message and player helpers
        code = """
tw.story.show_message("You picked up the chocolate.")
tw.player.damage(5)
tw.player.add_item("BONUS_COIN", "Bonus Coin")
tw.scene.set_attribute("found_secret", True)
"""
        msgs = await manager._execute_inline_script(code, "on_pickup", "CHOCOLATE")
        assert "You picked up the chocolate." in msgs
        assert avatar.hp == 95
        assert any(i.get("id") == "BONUS_COIN" for i in avatar.inventory)
        assert (
            manager.state.entity_states["__script_vars__"]["__scene_attr_LAB_found_secret"] is True
        )


@pytest.mark.asyncio
async def test_script_npc_operations_in_turn_manager(setup_test_db):
    from backend.models.world_entity import WorldEntity

    async with TestSessionLocal() as db_session:
        user = User(
            id="user_npc_test",
            username="npc_tester",
            hashed_password="fake",
            role="user",
        )
        db_session.add(user)
        await db_session.flush()

        adv = AdventureTemplate(
            id="adv_npc_test",
            title="NPC Script Test",
            owner_id=user.id,
            is_ready=True,
            original_manifest={"title": "Manifest", "scripts": []},
        )
        db_session.add(adv)

        avatar = Avatar(
            id="avatar_npc_test",
            name="Arthur",
            user_id=user.id,
            hp=100,
            mana=50,
            stamina=100,
            inventory=[],
        )
        db_session.add(avatar)

        state = SessionState(
            id="state_npc_test",
            session_id="session_npc_test",
            user_id=user.id,
            template_id=adv.id,
            avatar_id=avatar.id,
            current_scene_id="LAB",
            entity_states={},
            exit_states={},
        )
        db_session.add(state)

        # NPC in DUNGEON with an item
        npc_mara = WorldEntity(
            id="NPC_MARA",
            session_id="session_npc_test",
            name="Mara",
            description="A traveling scholar.",
            entity_type="NPC",
            current_scene_id="DUNGEON",
            hp=40,
            inventory=[{"id": "KEY_RUSTY", "name": "Rusty Key"}],
        )
        db_session.add(npc_mara)

        # Object in LAB
        item_potion = WorldEntity(
            id="ITEM_POTION",
            session_id="session_npc_test",
            name="Health Potion",
            description="A glowing health potion.",
            entity_type="OBJECT",
            current_scene_id="LAB",
            is_in_inventory=False,
            is_hidden=False,
            inventory=[],
        )
        db_session.add(item_potion)
        await db_session.flush()

        manager = GameTurnManager(db=db_session, user=user, game_id="session_npc_test")
        manager.adventure = adv
        manager.avatar = avatar
        manager.state = state

        script = """
# 1. NPC Speech
tw.npcs.say("NPC_MARA", "I arrived from the dungeon!")

# 2. Move NPC to protagonist's current scene
tw.npcs.move("NPC_MARA", "current")

# 3. Item transfers
tw.npcs.drop_item("NPC_MARA", "KEY_RUSTY")
tw.npcs.give_item("NPC_MARA", "ITEM_POTION")

# 4. NPC Defeat / Kill
tw.npcs.kill("NPC_MARA")
"""
        msgs = await manager._execute_inline_script(script, "test", "NPC_MARA")

        # 1. Verify speech message
        assert 'Mara: "I arrived from the dungeon!"' in msgs

        # 2. Verify NPC moved to LAB
        assert manager.state.entity_states["NPC_MARA"]["current_scene_id"] == "LAB"
        assert npc_mara.current_scene_id == "LAB"

        # 3. Verify dropped item in LAB
        assert manager.state.entity_states["KEY_RUSTY"]["current_scene_id"] == "LAB"
        assert manager.state.entity_states["KEY_RUSTY"]["is_in_inventory"] is False

        # 4. Verify NPC killed
        assert manager.state.entity_states["NPC_MARA"]["hp"] == 0
        assert manager.state.entity_states["NPC_MARA"]["is_defeated"] is True
        assert npc_mara.hp == 0
        assert npc_mara.metadata_json.get("is_defeated") is True


@pytest.mark.asyncio
async def test_narrate_raw_is_persisted_as_raw_chat_message(setup_test_db):
    from sqlalchemy import select

    from backend.models.chat import ChatMessage

    async with TestSessionLocal() as db_session:
        # Arrange
        manager = await _build_test_turn_manager(db_session, [], "sess_narrate_raw")
        ctx = await manager._build_script_context()
        manager._get_script_runner().execute_code(
            'tw.story.narrate_raw("Anchor: \\"Live!\\"")\ntw.story.narrate("Parsed.")',
            {"tw": ctx},
        )

        # Act
        returned = await manager._apply_script_changeset(ctx.changeset)

        # Assert
        assert [getattr(m, "raw", False) for m in returned] == [True, False]
        rows = (
            (
                await db_session.execute(
                    select(ChatMessage)
                    .where(ChatMessage.session_id == "sess_narrate_raw")
                    .order_by(ChatMessage.created_at)
                )
            )
            .scalars()
            .all()
        )
        assert [(m.content, m.to_client_dict()["raw"]) for m in rows] == [
            ('Anchor: "Live!"', True),
            ("Parsed.", False),
        ]
