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
    assert 'as a separate dialogue line Bram: "..."' in direction
    assert direction.endswith("Content: sings Yellow Submarine")


def test_choice_dialog_narration_asks_for_dialogue_lines():
    # Arrange
    from backend.api.routes.adventures.dialog_service import _NARRATION_SYSTEM_PROMPT

    # Act / Assert
    assert 'Character Name: "Dialogue"' in _NARRATION_SYSTEM_PROMPT
    assert "never quote speech inside a prose sentence" in _NARRATION_SYSTEM_PROMPT


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


def test_is_with_player_and_speech_silenced_outside_scene():
    # Arrange
    ctx = GameContext(
        avatar_data={"name": "Alex"},
        current_scene_id="ENTRY_HALL",
        entities={
            "CAT": {
                "id": "CAT",
                "name": "Schrödinger",
                "entity_type": "NPC",
                "current_scene_id": "TIME_MACHINE_LAB",
            },
            "VERA": {
                "id": "VERA",
                "name": "Vera",
                "entity_type": "NPC",
                "current_scene_id": "ENTRY_HALL",
            },
        },
    )

    # Act
    _run(
        ctx,
        "tw.vars.set('cat_with_player', tw.npcs.get('CAT').is_with_player)\n"
        "tw.vars.set('vera_with_player', tw.npcs.get('VERA').is_with_player)\n"
        "tw.npcs.say('CAT', 'Miao!')\n"
        "tw.npcs.say('VERA', 'Welcome.')\n"
        "tw.npcs.say_directed('CAT', 'purrs on the coil')\n"
        "tw.npcs.say_directed('VERA', 'sighs deeply')\n",
    )

    # Assert
    assert ctx.changeset.var_updates["cat_with_player"] is False
    assert ctx.changeset.var_updates["vera_with_player"] is True
    # Cat's speech and direction are suppressed; Vera's are kept
    assert ctx.changeset.narrative_messages == ['Vera: "Welcome."']
    assert len(ctx.changeset.gm_directions) == 1
    assert "Vera (VERA) speaks in this narration" in ctx.changeset.gm_directions[0]


def test_speech_allowed_after_moving_to_player():
    # Arrange
    ctx = GameContext(
        avatar_data={"name": "Alex"},
        current_scene_id="ENTRY_HALL",
        entities={
            "CAT": {
                "id": "CAT",
                "name": "Schrödinger",
                "entity_type": "NPC",
                "current_scene_id": "TIME_MACHINE_LAB",
            }
        },
    )

    # Act
    _run(
        ctx,
        "tw.npcs.get('CAT').move_to_player()\n"
        "tw.vars.set('cat_with_player_after_move', tw.npcs.get('CAT').is_with_player)\n"
        "tw.npcs.say('CAT', 'Miao!')\n",
    )

    # Assert
    assert ctx.changeset.var_updates["cat_with_player_after_move"] is True
    assert ctx.changeset.narrative_messages == ['Schrödinger: "Miao!"']


def test_say_directed_callback_still_queued_when_npc_absent():
    # Arrange
    ctx = GameContext(
        avatar_data={"name": "Alex"},
        current_scene_id="ENTRY_HALL",
        entities={
            "CAT": {
                "id": "CAT",
                "name": "Schrödinger",
                "entity_type": "NPC",
                "current_scene_id": "TIME_MACHINE_LAB",
            }
        },
    )

    # Act: callback 'on_after' is queued, but direction text is dropped
    _run(ctx, "tw.npcs.say_directed('CAT', 'purrs', after='on_after', after_args={'x': 1})")

    # Assert
    assert ctx.changeset.gm_directions == []
    assert ctx.changeset.after_narration == [{"handler": "on_after", "args": {"x": 1}}]
