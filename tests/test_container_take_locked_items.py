"""Take-locked items inside an open container stay there until a script unlocks them."""

from sqlalchemy import select

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.models.avatar import Avatar
from backend.models.world_entity import WorldEntity
from tests.test_game_loop import _seed_game_context


def _item(state, item_id: str, name: str, *, locked: bool) -> WorldEntity:
    return WorldEntity(
        id=item_id,
        session_id=state.session_id,
        entity_type="OBJECT",
        name=name,
        description=f"{name} at the bottom of the tank.",
        current_scene_id=state.current_scene_id,
        item_type="TOOL",
        is_hidden=False,
        is_in_inventory=False,
        is_portable=True,
        inventory=[],
        metadata_json={"locked": locked},
    )


async def _seed_tank(db, state) -> None:
    tank = WorldEntity(
        id="TANK",
        session_id=state.session_id,
        entity_type="OBJECT",
        name="Aquarium",
        description="A tank full of piranhas.",
        current_scene_id=state.current_scene_id,
        item_type="CONTAINER",
        is_hidden=False,
        is_in_inventory=False,
        is_portable=False,
        inventory=["WRENCH", "PEBBLE"],
    )
    db.add_all(
        [
            tank,
            _item(state, "WRENCH", "Golden Wrench", locked=True),
            _item(state, "PEBBLE", "Pebble", locked=False),
        ]
    )
    await db.commit()


async def _play(manager: GameTurnManager, message: str) -> list[str]:
    return [chunk async for chunk in manager.process_turn(message)]


async def _carried_ids(db, avatar_id: str) -> set[str]:
    avatar = (await db.execute(select(Avatar).where(Avatar.id == avatar_id))).scalars().one()
    await db.refresh(avatar)
    return {
        str(entry.get("id") if isinstance(entry, dict) else entry)
        for entry in avatar.inventory or []
    }


async def test_take_all_leaves_take_locked_items_in_the_container(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        # Arrange
        user, _adv, avatar, state = await _seed_game_context(db)
        await _seed_tank(db, state)

        # Act
        await _play(GameTurnManager(db, state.session_id, user), "/container_take_all Aquarium")

        # Assert
        carried = await _carried_ids(db, avatar.id)
        assert "PEBBLE" in carried
        assert "WRENCH" not in carried


async def test_take_item_refuses_a_take_locked_item(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        # Arrange
        user, _adv, avatar, state = await _seed_game_context(db)
        await _seed_tank(db, state)

        # Act
        chunks = await _play(
            GameTurnManager(db, state.session_id, user),
            "/container_take_item Aquarium | Golden Wrench",
        )

        # Assert
        assert any("locked" in c for c in chunks)
        assert "WRENCH" not in await _carried_ids(db, avatar.id)


async def test_unlocked_item_can_be_taken_from_the_container(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        # Arrange: a script unlocked the wrench (session override wins over the template flag)
        user, _adv, avatar, state = await _seed_game_context(db)
        await _seed_tank(db, state)
        states = dict(state.entity_states or {})
        states["WRENCH"] = {"locked": False}
        state.entity_states = states
        await db.commit()

        # Act
        await _play(
            GameTurnManager(db, state.session_id, user),
            "/container_take_item Aquarium | Golden Wrench",
        )

        # Assert
        assert "WRENCH" in await _carried_ids(db, avatar.id)


async def test_drop_to_scene_keeps_take_locked_items_in_the_container(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        # Arrange
        user, _adv, _avatar, state = await _seed_game_context(db)
        await _seed_tank(db, state)

        # Act
        await _play(GameTurnManager(db, state.session_id, user), "/container_drop_scene Aquarium")

        # Assert
        await db.refresh(state)
        tank_inventory = (state.entity_states.get("TANK") or {}).get("inventory")
        tank_ids = [
            entry.get("id") if isinstance(entry, dict) else entry for entry in tank_inventory
        ]
        assert tank_ids == ["WRENCH"]
