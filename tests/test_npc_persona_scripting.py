import pytest
from sqlalchemy import select

from backend.engine.interaction.location_context import build_location_context
from backend.engine.interaction.trigger_service import TriggerService
from backend.engine.scripting.context import GameContext
from backend.engine.scripting.npc_persona import MAX_PERSONA_LENGTH
from backend.engine.scripting.runner import ScriptRunner
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldEntity, WorldScene
from tests.conftest import TestSessionLocal


def _context(character: str = "Friendly, talkative") -> GameContext:
    return GameContext(
        avatar_data={"name": "Hero"},
        current_scene_id="TAVERN",
        entities={
            "INNKEEPER": {
                "id": "INNKEEPER",
                "name": "Brom",
                "entity_type": "NPC",
                "character": character,
                "goal": "Keep the tavern running",
            }
        },
    )


def _run(ctx: GameContext, code: str) -> None:
    ScriptRunner([]).execute_code(code, {"tw": ctx}, script_id="test")


def test_set_character_replaces_the_personality():
    # Arrange
    ctx = _context()

    # Act
    _run(ctx, "tw.npcs.set_character('INNKEEPER', '  Hostile,   rude ')")

    # Assert
    assert ctx.npcs.get("INNKEEPER").character == "Hostile, rude"
    assert {"entity_id": "INNKEEPER", "character": "Hostile, rude"} in ctx.changeset.entity_updates


def test_character_and_goal_are_assignable_properties():
    # Arrange
    ctx = _context()

    # Act
    _run(
        ctx,
        "npc = tw.npcs.get('INNKEEPER')\n"
        "npc.character = 'Gloomy'\n"
        "npc.goal = 'Get revenge on the hero'\n",
    )

    # Assert
    npc = ctx.npcs.get("INNKEEPER")
    assert npc.character == "Gloomy"
    assert npc.goal == "Get revenge on the hero"


def test_add_and_remove_trait():
    # Arrange
    ctx = _context()

    # Act
    _run(
        ctx,
        "tw.npcs.add_trait('INNKEEPER', 'drunk')\n"
        "tw.npcs.add_trait('INNKEEPER', 'DRUNK')\n"
        "tw.npcs.remove_trait('INNKEEPER', 'talkative')\n"
        "if tw.npcs.get('INNKEEPER').has_trait('Drunk'):\n"
        "    tw.vars.set('is_drunk', True)\n",
    )

    # Assert
    assert ctx.npcs.get("INNKEEPER").character == "Friendly, drunk"
    assert ctx.changeset.var_updates.get("is_drunk") is True


def test_persona_text_is_capped_and_empty_clears_it():
    # Arrange
    ctx = _context()
    npc = ctx.npcs.get("INNKEEPER")

    # Act
    npc.set_goal("x" * (MAX_PERSONA_LENGTH + 50))
    npc.set_character("")

    # Assert
    assert len(npc.goal) == MAX_PERSONA_LENGTH
    assert npc.character == ""
    assert ctx.changeset.entity_updates[-1] == {"entity_id": "INNKEEPER", "character": None}


@pytest.mark.asyncio
async def test_trigger_script_changes_reach_the_gm_location_context(setup_test_db):
    # Arrange
    async with TestSessionLocal() as db:
        scene = WorldScene(id="TAVERN", session_id="sess_persona", label="Tavern", description="")
        npc = WorldEntity(
            id="INNKEEPER",
            session_id="sess_persona",
            entity_type="NPC",
            name="Brom",
            description="The innkeeper.",
            current_scene_id="TAVERN",
            character="Friendly",
        )
        db.add_all([scene, npc])
        await db.commit()
        state = SessionState(session_id="sess_persona", current_scene_id="TAVERN", entity_states={})

        # Act
        await TriggerService.execute_trigger(
            db,
            state,
            trigger_name="on_interact",
            target_id="INNKEEPER",
            script_code="tw.npcs.set_character('INNKEEPER', 'Hostile; short, rude answers')",
        )
        await db.commit()

    # Assert
    async with TestSessionLocal() as db:
        row = (
            await db.execute(select(WorldEntity).where(WorldEntity.session_id == "sess_persona"))
        ).scalar_one()
        scene_row = (await db.execute(select(WorldScene))).scalar_one()
        assert row.character == "Hostile; short, rude answers"
        assert state.entity_states["INNKEEPER"]["character"] == "Hostile; short, rude answers"
        prompt = build_location_context(scene_row, [row], [])
        assert "[Character: Hostile; short, rude answers]" in prompt


@pytest.mark.asyncio
async def test_turn_script_changes_are_written_to_the_npc_row(setup_test_db):
    from tests.test_script_turn_integration import _build_test_turn_manager

    async with TestSessionLocal() as db:
        # Arrange
        manager = await _build_test_turn_manager(db, [], session_id="sess_turn_persona")
        db.add(
            WorldEntity(
                id="INNKEEPER",
                session_id="sess_turn_persona",
                entity_type="NPC",
                name="Brom",
                description="The innkeeper.",
                current_scene_id="SCENE_START",
                character="Friendly",
            )
        )
        await db.commit()
        ctx = await manager._build_script_context()
        _run(
            ctx,
            "tw.npcs.add_trait('INNKEEPER', 'drunk')\ntw.npcs.set_goal('INNKEEPER', 'More ale')",
        )

        # Act
        await manager._apply_script_changeset(ctx.changeset)
        await db.commit()

    # Assert
    async with TestSessionLocal() as db:
        row = (
            await db.execute(
                select(WorldEntity).where(WorldEntity.session_id == "sess_turn_persona")
            )
        ).scalar_one()
        assert row.character == "Friendly, drunk"
        assert row.goal == "More ale"
