from backend.engine.scripting.context import GameContext, TurnProxy
from backend.engine.scripting.runner import ScriptRunner


def test_turn_proxy_properties():
    turn = TurnProxy(player_message="  paint a green dragon  ", language="en")
    assert turn.player_message == "paint a green dragon"
    assert turn.message == "paint a green dragon"
    assert turn.language == "en"


def test_game_context_turn_proxy_integration():
    ctx = GameContext(player_message="Paint a dog", language="de")
    assert ctx.turn.player_message == "Paint a dog"
    assert ctx.turn.message == "Paint a dog"
    assert ctx.turn.language == "de"
    assert ctx.player_message == "Paint a dog"


def test_script_runner_exposes_player_message_in_scope():
    runner = ScriptRunner([])
    ctx = GameContext(player_message="draw a tiny elephant")
    code = """
tw.vars.set("captured_message", tw.turn.player_message)
tw.vars.set("captured_alias", tw.player_message)
tw.vars.set("captured_var", player_message)
"""
    scope = {"tw": ctx, "game": ctx}
    runner.execute_code(code, scope)
    assert ctx.changeset.var_updates["captured_message"] == "draw a tiny elephant"
    assert ctx.changeset.var_updates["captured_alias"] == "draw a tiny elephant"
    assert ctx.changeset.var_updates["captured_var"] == "draw a tiny elephant"
