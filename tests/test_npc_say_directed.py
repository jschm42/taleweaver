"""tw.npcs.say_directed: an NPC speaks in the next narration, worded by the GM."""

from backend.engine.scripting.context import GameContext
from backend.engine.scripting.gm_directions import MAX_DIRECTION_LENGTH
from backend.engine.scripting.runner import ScriptRunner


def _context() -> GameContext:
    return GameContext(
        avatar_data={"name": "Hero"},
        current_scene_id="TAVERN",
        entities={"BRAM": {"id": "BRAM", "name": "Bram", "entity_type": "NPC"}},
    )


def _run(ctx: GameContext, code: str) -> None:
    ScriptRunner([]).execute_code(code, {"tw": ctx}, script_id="test")


def test_say_directed_queues_a_gm_direction_for_the_npc():
    # Arrange
    ctx = _context()

    # Act
    _run(ctx, "tw.npcs.say_directed('BRAM', 'sings Yellow Submarine')")

    # Assert
    assert ctx.changeset.narrative_messages == []
    [direction] = ctx.changeset.gm_directions
    assert direction.startswith("Bram (BRAM) speaks in this narration")
    assert direction.endswith("Content: sings Yellow Submarine")


def test_say_directed_works_on_the_npc_proxy():
    # Arrange
    ctx = _context()

    # Act
    _run(ctx, "tw.npcs.get('bram').say_directed('warns the player about the storm')")

    # Assert
    assert ctx.changeset.gm_directions[0].endswith("Content: warns the player about the storm")


def test_say_directed_ignores_an_empty_direction():
    # Arrange
    ctx = _context()

    # Act
    _run(ctx, "tw.npcs.say_directed('BRAM', '   ')")

    # Assert
    assert ctx.changeset.gm_directions == []


def test_say_directed_caps_the_direction_length():
    # Arrange
    ctx = _context()

    # Act
    _run(ctx, "tw.npcs.say_directed('BRAM', 'x' * 2000)")

    # Assert
    assert len(ctx.changeset.gm_directions[0]) == MAX_DIRECTION_LENGTH
