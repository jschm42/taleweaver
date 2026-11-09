"""Debug world map actions: ``/debug goto SCENE`` and ``/debug open_exit EXIT_ID``."""

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.models.world_entity import WorldExit, WorldScene
from tests.test_game_loop import _seed_game_context


async def _seed_world(db, state) -> None:
    db.add_all(
        [
            WorldScene(id="START", session_id=state.session_id, label="Start", description="."),
            WorldScene(
                id="VAULT",
                session_id=state.session_id,
                label="Vault",
                description="A sealed vault.",
                on_enter_scene_text="The vault air is stale.",
            ),
            WorldExit(
                id="EXIT_VAULT",
                session_id=state.session_id,
                from_scene_id="START",
                to_scene_id="VAULT",
                label="steel door",
                exit_type="bidirectional",
                is_locked=True,
            ),
        ]
    )
    state.is_debug_enabled = True
    # A script lock on the route must not survive the debug unlock.
    state.exit_states = {"START:VAULT": {"is_locked": True}}
    await db.commit()


async def _play(manager: GameTurnManager, message: str) -> list[str]:
    return [chunk async for chunk in manager.process_turn(message)]


async def test_goto_moves_the_player_and_fires_arrival(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        # Arrange
        user, _adv, _avatar, state = await _seed_game_context(db)
        await _seed_world(db, state)

        # Act: the exit is locked, goto ignores it
        chunks = await _play(GameTurnManager(db, state.session_id, user), "/debug goto vault")

        # Assert
        await db.refresh(state)
        assert state.current_scene_id == "VAULT"
        assert any("event: scene_transition" in c for c in chunks)
        assert any("The vault air is stale." in c for c in chunks)


async def test_goto_unknown_scene_keeps_the_player(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        # Arrange
        user, _adv, _avatar, state = await _seed_game_context(db)
        await _seed_world(db, state)

        # Act
        chunks = await _play(GameTurnManager(db, state.session_id, user), "/debug goto NOWHERE")

        # Assert
        await db.refresh(state)
        assert state.current_scene_id == "START"
        assert any("not found" in c for c in chunks)
        assert not any("event: scene_transition" in c for c in chunks)


async def test_open_exit_unlocks_row_and_route_override(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        # Arrange
        user, _adv, _avatar, state = await _seed_game_context(db)
        await _seed_world(db, state)

        # Act
        await _play(GameTurnManager(db, state.session_id, user), "/debug open_exit EXIT_VAULT")

        # Assert
        await db.refresh(state)
        world_exit = await db.get(WorldExit, "EXIT_VAULT")
        await db.refresh(world_exit)
        assert world_exit.is_locked is False
        assert state.exit_states["START:VAULT"]["is_locked"] is False
        assert state.exit_states["EXIT_VAULT"]["is_locked"] is False
