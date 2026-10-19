import pytest

from backend.core.auth import create_access_token
from backend.engine.scripting.context import GameContext
from backend.engine.scripting.runner import ScriptRunner
from backend.engine.switch_service import SwitchService
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.models.world_entity import WorldScene
from tests.conftest import TestSessionLocal


def _auth_headers(username: str) -> dict:
    token = create_access_token(data={"sub": username})
    return {"Authorization": f"Bearer {token}"}


async def _seed_template(username: str) -> tuple[str, str]:
    user = User(username=username, hashed_password="x", role="admin")
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        user_id = user.id
        tpl_id = f"tpl-switch-trig-{username}"
        tpl = AdventureTemplate(
            id=tpl_id,
            owner_id=user_id,
            title="Switch Triggers Test",
            version="1.0",
            rule_enforcement_mode="rpg",
            is_ready=True,
            creation_status="Ready",
            generate_scene_images=False,
            generate_npc_images=False,
            generate_item_images=False,
            teaser="t",
            rules="r",
            plot="p",
            intro_text="i",
            walkthrough="w",
            completed_condition="done",
            gameover_condition="lost",
            tts_director_notes="notes",
            quests=[],
        )
        db.add(tpl)
        scene = WorldScene(
            id="SCENE_OVEN", template_id=tpl_id, label="Kitchen", description="Kitchen"
        )
        db.add(scene)
        await db.commit()
    return user_id, tpl_id


def test_switch_service_evaluate_expression():
    """Verify deterministic boolean expression evaluation in sandboxed script context."""
    variables = {"microwave_safe": True, "sink_fixed": False}
    story_flags = {"door_unlocked": True}
    avatar = {"hp": 85, "max_hp": 100}

    ctx = GameContext(
        variables=variables,
        avatar_data=avatar,
        story_flags=story_flags,
    )

    # 1. True condition
    passed, err = SwitchService.evaluate_gate_expression(
        "tw.vars.get('microwave_safe') == True", ctx
    )
    assert passed is True
    assert err is None

    # 2. False condition
    passed, err = SwitchService.evaluate_gate_expression("tw.vars.get('sink_fixed') == True", ctx)
    assert passed is False
    assert "evaluated to false" in err

    # 3. Compound condition
    passed, err = SwitchService.evaluate_gate_expression(
        "tw.vars.get('microwave_safe') and tw.vars.get('sink_fixed')",
        ctx,
    )
    assert passed is False

    # 4. Proxy check via tw.flags
    passed, err = SwitchService.evaluate_gate_expression(
        "tw.flags.get('door_unlocked') == True", ctx
    )
    assert passed is True
    assert err is None

    # 5. Player stat check
    passed, err = SwitchService.evaluate_gate_expression("tw.player.hp > 50", ctx)
    assert passed is True

    # 6. Syntax error safety
    passed, err = SwitchService.evaluate_gate_expression("invalid == syntax ==", ctx)
    assert passed is False
    assert "Guard expression" in err


def test_switch_service_transition_gates_and_fail_message():
    """Verify transition gates evaluation with custom fail message."""
    variables = {"power_restored": False}
    ctx = GameContext(variables=variables)

    transition = {
        "from": "OFF",
        "to": "HEATING",
        "gates": {
            "expression": "tw.vars.get('power_restored') == True",
        },
        "fail_message": "Arthur insists the sink and microwave must be safe first.",
    }

    # Should fail because power_restored is False
    passed, fail_msg = SwitchService.evaluate_transition_gates(
        transition=transition,
        context=ctx,
        switch_name="Oven",
    )
    assert passed is False
    assert fail_msg == "Arthur insists the sink and microwave must be safe first."

    # Update variable to True
    ctx.vars.set("power_restored", True)
    passed, fail_msg = SwitchService.evaluate_transition_gates(
        transition=transition,
        context=ctx,
        switch_name="Oven",
    )
    assert passed is True
    assert fail_msg == ""


def test_switch_service_triggers_execution():
    """Verify switch-level and transition-level script triggers on success and failure."""
    runner = ScriptRunner()
    variables = {"oven_triggered": False, "trans_triggered": False, "fail_count": 0}
    ctx = GameContext(variables=variables)

    config = {
        "on_success_script": "tw.vars.set('oven_triggered', True)",
        "on_failure_script": "tw.vars.set('fail_count', tw.vars.get('fail_count', 0) + 1)",
    }
    transition = {
        "on_success_script": "tw.vars.set('trans_triggered', True)",
        "on_failure_script": "tw.vars.set('fail_count', tw.vars.get('fail_count', 0) + 10)",
    }

    # Test Success execution
    SwitchService.execute_transition_triggers(
        runner=runner,
        config=config,
        transition=transition,
        success=True,
        context=ctx,
        switch_id="OVEN",
    )
    assert ctx.vars.get("oven_triggered") is True
    assert ctx.vars.get("trans_triggered") is True
    assert ctx.vars.get("fail_count") == 0

    # Test Failure execution
    SwitchService.execute_transition_triggers(
        runner=runner,
        config=config,
        transition=transition,
        success=False,
        context=ctx,
        switch_id="OVEN",
    )
    # 0 + 10 (transition) + 1 (global) = 11
    assert ctx.vars.get("fail_count") == 11


@pytest.mark.asyncio
async def test_editor_switch_scripts_persistence(client, setup_test_db):
    """Verify saving switch with scripted gates, on_success_script, and on_failure_script via Editor API."""
    user_id, tpl_id = await _seed_template("switch_script_editor")
    headers = _auth_headers("switch_script_editor")

    switch_payload = {
        "entity_id": "OVEN",
        "scene_id": "SCENE_OVEN",
        "entity_type": "OBJECT",
        "item_type": "SWITCH",
        "name": "Industrial Oven",
        "description": "A high-temperature oven.",
        "on_success_script": "tw.vars.set('kitchen_heated', True)",
        "on_failure_script": "tw.player.damage(5)",
        "metadata_json": {
            "switch": {
                "states": ["OFF", "HEATING", "BAKING"],
                "initial_state": "OFF",
                "on_success_script": "tw.vars.set('kitchen_heated', True)",
                "on_failure_script": "tw.player.damage(5)",
                "transitions": [
                    {
                        "from": "OFF",
                        "to": "HEATING",
                        "gates": {
                            "expression": "tw.vars.get('sink_fixed') and tw.vars.get('microwave_safe')",
                        },
                        "fail_message": "Arthur insists that the sink and smoking microwave must be made safe first.",
                        "success_message": "The oven hums to life with a warm red glow.",
                        "on_success_script": "tw.vars.set('oven_turned_on', True)",
                        "on_failure_script": "tw.story.narrate('The oven sparks violently.')",
                    }
                ],
            }
        },
    }

    res = await client.post(
        f"/api/adventures/{tpl_id}/editor/entity",
        headers=headers,
        json=switch_payload,
    )
    assert res.status_code == 200, res.text
    saved_meta = res.json()["entity"]["metadata_json"]
    sw = saved_meta["switch"]

    assert sw["on_success_script"] == "tw.vars.set('kitchen_heated', True)"
    assert sw["on_failure_script"] == "tw.player.damage(5)"
    assert len(sw["transitions"]) == 1
    t0 = sw["transitions"][0]
    assert (
        t0["gates"]["expression"] == "tw.vars.get('sink_fixed') and tw.vars.get('microwave_safe')"
    )
    assert t0["success_message"] == "The oven hums to life with a warm red glow."
    assert t0["on_success_script"] == "tw.vars.set('oven_turned_on', True)"
    assert t0["on_failure_script"] == "tw.story.narrate('The oven sparks violently.')"


def test_scripting_engine_switch_read_write():
    """Verify scripting engine can read and write switch states via tw.switches and tw.objects."""
    entities = {
        "LEVER_01": {
            "id": "LEVER_01",
            "name": "Rusty Lever",
            "item_type": "SWITCH",
            "metadata_json": {
                "switch": {
                    "states": ["UP", "DOWN"],
                    "initial_state": "UP",
                }
            },
        },
        "VALVE_A": {
            "id": "VALVE_A",
            "name": "Steam Valve",
            "item_type": "SWITCH",
            "switch_state": "CLOSED",
            "metadata_json": {
                "switch": {
                    "states": ["CLOSED", "HALF", "OPEN"],
                    "initial_state": "CLOSED",
                }
            },
        },
    }

    ctx = GameContext(entities=entities)
    runner = ScriptRunner([])

    # 1. Reading initial and existing states
    assert ctx.switches.get_state("LEVER_01") == "UP"
    assert ctx.switches.get_state("VALVE_A") == "CLOSED"
    assert ctx.switches["LEVER_01"] == "UP"
    assert ctx.switches.is_state("LEVER_01", "UP") is True
    assert ctx.switch("LEVER_01").state == "UP"
    assert ctx.objects.get("LEVER_01").state == "UP"
    assert ctx.objects.get("LEVER_01").is_switch is True

    # 2. Writing via script execution
    script = """
if tw.switches.get_state("LEVER_01") == "UP":
    tw.switches.set_state("LEVER_01", "DOWN")
    tw.story.narrate("You pull the rusty lever down.")

tw.switches["VALVE_A"] = "OPEN"
tw.objects.get("LEVER_01").state = "DOWN"
"""
    scope = {"tw": ctx, "game": ctx}
    runner.execute_code(script, scope)

    # 3. Reading back modified states immediately in script context
    assert ctx.switches.get_state("LEVER_01") == "DOWN"
    assert ctx.switches["VALVE_A"] == "OPEN"
    assert ctx.switch("LEVER_01").is_state("DOWN") is True
    assert ctx.objects.get("LEVER_01").state == "DOWN"
    assert ctx.objects.get("VALVE_A").switch_state == "OPEN"

    # 4. Check changeset mutations
    updates = {
        u["entity_id"]: u["switch_state"]
        for u in ctx.changeset.entity_updates
        if "switch_state" in u
    }
    assert updates["LEVER_01"] == "DOWN"
    assert updates["VALVE_A"] == "OPEN"
    assert "You pull the rusty lever down." in ctx.changeset.narrative_messages


def test_scripting_engine_switch_flip_and_outcomes():
    """Verify tw.switches.flip, toggle, and outcome triggering from script."""
    entities = {
        "SECRET_SWITCH": {
            "id": "SECRET_SWITCH",
            "name": "Secret Switch",
            "item_type": "SWITCH",
            "metadata_json": {
                "switch": {
                    "states": ["OFF", "ON"],
                    "initial_state": "OFF",
                    "outcomes": [
                        {
                            "on_state": "ON",
                            "effects": [
                                {"type": "story_flag", "key": "SECRET_ROOM_REVEALED"},
                                {"type": "unlock_exit", "target_id": "EXIT_SECRET"},
                            ],
                        }
                    ],
                }
            },
        }
    }
    exit_states = {"HALL:EXIT_SECRET": {"is_locked": True}}
    ctx = GameContext(entities=entities, exit_states=exit_states)
    runner = ScriptRunner([])

    script = """
sw = tw.switch("SECRET_SWITCH")
if sw.state == "OFF":
    new_state = sw.flip()
    tw.vars.set("flip_result", new_state)
"""
    scope = {"tw": ctx, "game": ctx}
    runner.execute_code(script, scope)

    assert ctx.vars.get("flip_result") == "ON"
    assert ctx.switches.get_state("SECRET_SWITCH") == "ON"
    # Outcomes applied:
    assert ctx.flags.get("SECRET_ROOM_REVEALED") is True
    assert any(
        upd.get("to_scene_id") == "EXIT_SECRET" and upd.get("is_locked") is False
        for upd in ctx.changeset.exit_updates
    )
