import pytest

from backend.engine.scripting.context import GameContext
from backend.engine.scripting.runner import ScriptRunner
from backend.engine.scripting.sandbox import (
    SafeAstInterpreter,
    ScriptExecutionError,
    ScriptSecurityError,
    ScriptTimeoutError,
)


def test_sandbox_evaluates_basic_arithmetic_and_logic():
    interpreter = SafeAstInterpreter()
    code = """
x = 10 + 5 * 2
is_valid = x == 20
if is_valid:
    res = "success"
else:
    res = "failure"
"""
    ctx = {}
    interpreter.execute(code, ctx)
    assert ctx["x"] == 20
    assert ctx["is_valid"] is True
    assert ctx["res"] == "success"


def test_sandbox_blocks_imports():
    interpreter = SafeAstInterpreter()
    code = "import os"
    with pytest.raises(ScriptSecurityError) as exc:
        interpreter.execute(code, {})
    assert "Import" in str(exc.value)


def test_sandbox_blocks_import_from():
    interpreter = SafeAstInterpreter()
    code = "from os import system"
    with pytest.raises(ScriptSecurityError) as exc:
        interpreter.execute(code, {})
    assert "Import" in str(exc.value)


def test_sandbox_blocks_private_and_dunder_attributes():
    interpreter = SafeAstInterpreter()
    code = "cls = ().__class__"
    with pytest.raises(ScriptSecurityError) as exc:
        interpreter.execute(code, {})
    assert "forbidden" in str(exc.value).lower()


def test_sandbox_blocks_while_loops():
    interpreter = SafeAstInterpreter()
    code = """
while True:
    pass
"""
    with pytest.raises(ScriptSecurityError) as exc:
        interpreter.execute(code, {})
    assert "While" in str(exc.value)


def test_sandbox_instruction_limit_triggers_timeout():
    interpreter = SafeAstInterpreter(max_steps=100)
    code = """
x = 0
for i in range(1000):
    x = x + 1
"""
    with pytest.raises(ScriptTimeoutError):
        interpreter.execute(code, {})


def test_sandbox_memory_multiplication_guard():
    interpreter = SafeAstInterpreter()
    code = "huge = 'a' * 1000000"
    with pytest.raises(ScriptSecurityError):
        interpreter.execute(code, {})


def test_sandbox_supports_for_loops_and_lists():
    interpreter = SafeAstInterpreter()
    code = """
numbers = [1, 2, 3, 4, 5]
total = 0
for n in numbers:
    if n == 4:
        break
    total += n
"""
    ctx = {}
    interpreter.execute(code, ctx)
    assert ctx["total"] == 6


def test_game_context_proxy_mutations():
    avatar_data = {"name": "Hero", "hp": 100, "mana": 40, "stamina": 80, "inventory": [{"id": "COIN"}]}
    entities = {
        "NPC_GUARD": {"id": "NPC_GUARD", "name": "Guard", "npc_type": "HUMANOID", "hp": 50, "current_scene_id": "GATE"},
        "LEVER_1": {"id": "LEVER_1", "name": "Stone Lever", "switch_state": "OFF", "locked": False},
    }
    exit_states = {
        "ROOM_A:ROOM_B": {"is_locked": True}
    }
    quests = [{"id": "QUEST_MAIN", "status": "open"}]
    script_vars = {"visited_count": 1}

    context = GameContext(
        avatar_data=avatar_data,
        current_scene_id="ROOM_A",
        entities=entities,
        exit_states=exit_states,
        quests=quests,
        script_vars=script_vars,
    )

    code = """
# Test reading
if tw.scene.id == "ROOM_A":
    tw.vars.set("in_room_a", True)

if tw.player.has_item("COIN"):
    tw.player.remove_item("COIN")
    tw.player.give_item("KEY_GOLD")

tw.player.modify_hp(-15)
tw.player.add_status_effect("Poisoned")

# NPCs and Exits
guard = tw.npcs.get("NPC_GUARD")
guard.modify_hp(-20)
guard.move_to("DUNGEON", "in the cell")

lever = tw.objects.get("LEVER_1")
lever.set_state("ON")

tw.exits.unlock("ROOM_A", "ROOM_B")
tw.story.narrate("The iron gate swings open!")
tw.memories.add("The hero unlocked the secret gate.", emotion="positive")
tw.quests.complete("QUEST_MAIN")
tw.game.win("Victory!")
"""
    runner = ScriptRunner([{"id": "SCRIPT_TEST", "trigger": "on_enter_scene", "target_id": "ROOM_A", "code": code}])
    changeset = runner.run_trigger("on_enter_scene", context, target_id="ROOM_A")

    assert changeset.player_hp_change == -15
    assert "KEY_GOLD" in [item["id"] for item in changeset.player_new_items]
    assert "COIN" in changeset.player_removed_item_ids
    assert "Poisoned" in changeset.player_status_effects_add
    assert changeset.var_updates.get("in_room_a") is True

    # Entities & Exits
    assert any(m["entity_id"] == "NPC_GUARD" and m["to_scene_id"] == "DUNGEON" for m in changeset.entity_movements)
    assert any(u["entity_id"] == "NPC_GUARD" and u.get("hp") == 30 for u in changeset.entity_updates)
    assert any(u["entity_id"] == "LEVER_1" and u.get("switch_state") == "ON" for u in changeset.entity_updates)
    assert any(e["from_scene_id"] == "ROOM_A" and e["to_scene_id"] == "ROOM_B" and e["is_locked"] is False for e in changeset.exit_updates)

    # Narrative, Memories, Quest, Win
    assert "The iron gate swings open!" in changeset.narrative_messages
    assert len(changeset.new_memories) == 1
    assert "QUEST_MAIN" in changeset.completed_quest_ids
    assert changeset.game_completed is True


def test_check_syntax_valid_code():
    code = """
x = 10
if x > 5:
    tw.story.narrate("High value")
"""
    errors = SafeAstInterpreter.check_syntax(code)
    assert errors == []


def test_check_syntax_syntax_error():
    code = """
if x > 5
    print("missing colon")
"""
    errors = SafeAstInterpreter.check_syntax(code)
    assert len(errors) == 1
    assert "Syntax error at line 2" in errors[0]


def test_check_syntax_forbidden_import():
    code = "import os\nos.system('echo 1')"
    errors = SafeAstInterpreter.check_syntax(code)
    assert len(errors) >= 1
    assert any("Forbidden syntax 'Import'" in e for e in errors)


def test_check_syntax_forbidden_dunder():
    code = "secret = obj.__class__"
    errors = SafeAstInterpreter.check_syntax(code)
    assert len(errors) == 1
    assert "Access to private/dunder attribute '__class__' is forbidden" in errors[0]


def test_check_syntax_empty_code():
    assert SafeAstInterpreter.check_syntax("") == []
    assert SafeAstInterpreter.check_syntax("   \n\t  ") == []

