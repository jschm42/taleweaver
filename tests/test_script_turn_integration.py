import pytest
from tests.conftest import TestSessionLocal

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.session_state import SessionState
from backend.models.user import User


@pytest.mark.asyncio
async def test_script_triggers_in_turn_manager(setup_test_db):
    async with TestSessionLocal() as db_session:
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

        manifest = {
            "title": "Scripted Adventure",
            "scripts": scripts,
        }

        user = User(
            id="user_script_test",
            username="script_tester",
            hashed_password="fake",
            role="user",
        )
        db_session.add(user)
        await db_session.flush()

        adv = AdventureTemplate(
            id="adv_script_test",
            title="Scripted Adventure",
            owner_id=user.id,
            is_ready=True,
            rule_enforcement_mode="rpg",
            scripts_generation_enabled=True,
            original_manifest=manifest,
        )
        db_session.add(adv)
        await db_session.flush()

        avatar = Avatar(
            id="avatar_script_test",
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
            id="state_script_test",
            session_id="session_script_test",
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

        manager = GameTurnManager(db=db_session, user=user, game_id="session_script_test")
        manager.adventure = adv
        manager.avatar = avatar
        manager.state = state

        # Test 1: on_turn_start execution
        runner = manager._get_script_runner()
        assert len(runner.scripts) == 3

        ctx = await manager._build_script_context()
        cs = runner.run_trigger("on_turn_start", ctx)
        assert cs.var_updates.get("turn_counter") == 1
        assert "A cold draft blows through the corridor." in cs.narrative_messages

        # Apply changeset to session state
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
        assert any(e["from_scene_id"] == "SCENE_START" and e["to_scene_id"] == "SCENE_SECRET" and not e["is_locked"] for e in cs_lever.exit_updates)

        await manager._apply_script_changeset(cs_lever)
        assert manager.state.exit_states["SCENE_START:SCENE_SECRET"]["is_locked"] is False
