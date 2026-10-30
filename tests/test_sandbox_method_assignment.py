"""Assigning to a method (``npc.add_trait = "angry"``) fails loudly instead of doing nothing."""

import pytest

from backend.engine.scripting.context import GameContext
from backend.engine.scripting.sandbox import SafeAstInterpreter, ScriptExecutionError


def _context() -> GameContext:
    return GameContext(
        avatar_data={"name": "Hero"},
        current_scene_id="TAVERN",
        entities={
            "BRAM": {"id": "BRAM", "name": "Bram", "entity_type": "NPC", "character": "Calm"}
        },
    )


def _run(ctx: GameContext, code: str) -> None:
    SafeAstInterpreter().execute(code, {"tw": ctx})


@pytest.mark.parametrize(
    "code",
    [
        "npc = tw.npcs.get('BRAM')\nnpc.add_trait = 'very angry'",
        "tw.npcs.get('BRAM').remove_trait = 'calm'",
        "tw.story.narrate = 'Hello'",
    ],
)
def test_assigning_to_a_method_raises(code):
    # Act / Assert
    with pytest.raises(ScriptExecutionError, match="is a method and cannot be assigned"):
        _run(_context(), code)


def test_error_names_the_call_to_use_instead():
    # Act / Assert
    with pytest.raises(ScriptExecutionError, match=r"Call it instead: npc\.add_trait\(\.\.\.\)"):
        _run(_context(), "npc = tw.npcs.get('BRAM')\nnpc.add_trait = 'very angry'")


def test_properties_with_setters_stay_assignable():
    # Arrange
    ctx = _context()

    # Act
    _run(ctx, "npc = tw.npcs.get('BRAM')\nnpc.character = 'Very angry'")

    # Assert
    assert ctx.npcs.get("BRAM").character == "Very angry"
