"""Taking an item out of a container by name must not leave a copy behind in the container."""

from types import SimpleNamespace

from sqlalchemy import select

from backend.api.routes.adventures.container_detach import detach_from_containers
from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.models.avatar import Avatar
from backend.models.world_entity import WorldEntity
from tests.test_game_loop import _seed_game_context


async def _seed_fridge(db, state) -> None:
    db.add_all(
        [
            WorldEntity(
                id="FRIDGE",
                session_id=state.session_id,
                entity_type="OBJECT",
                name="Refrigerator",
                description="A humming fridge.",
                current_scene_id=state.current_scene_id,
                item_type="CONTAINER",
                is_hidden=False,
                is_in_inventory=False,
                is_portable=False,
                inventory=["FROZEN_BLOCK"],
            ),
            WorldEntity(
                id="FROZEN_BLOCK",
                session_id=state.session_id,
                entity_type="OBJECT",
                name="Frozen Block",
                description="Rock-hard casserole.",
                current_scene_id=state.current_scene_id,
                item_type="PICKABLE",
                is_hidden=False,
                is_in_inventory=False,
                is_portable=True,
                inventory=[],
            ),
        ]
    )
    await db.commit()


async def _play(manager: GameTurnManager, message: str) -> list[str]:
    return [chunk async for chunk in manager.process_turn(message)]


async def _carried_count(db, avatar_id: str, item_id: str) -> int:
    avatar = (await db.execute(select(Avatar).where(Avatar.id == avatar_id))).scalars().one()
    await db.refresh(avatar)
    return sum(
        1
        for entry in avatar.inventory or []
        if (entry.get("id") if isinstance(entry, dict) else entry) == item_id
    )


async def test_take_by_name_then_take_all_does_not_duplicate(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        # Arrange
        user, _adv, avatar, state = await _seed_game_context(db)
        await _seed_fridge(db, state)

        # Act
        await _play(GameTurnManager(db, state.session_id, user), "/take Frozen Block")
        await _play(GameTurnManager(db, state.session_id, user), "/container_take_all Refrigerator")

        # Assert
        assert await _carried_count(db, avatar.id, "FROZEN_BLOCK") == 1


async def test_take_item_from_container_skips_an_item_already_carried(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        # Arrange: a stale container entry from before the fix
        user, _adv, avatar, state = await _seed_game_context(db)
        await _seed_fridge(db, state)
        await _play(GameTurnManager(db, state.session_id, user), "/take Frozen Block")
        stale = dict(state.entity_states or {})
        stale["FRIDGE"] = {"inventory": ["FROZEN_BLOCK"]}
        state.entity_states = stale
        await db.commit()

        # Act
        chunks = await _play(
            GameTurnManager(db, state.session_id, user),
            "/container_take_item Refrigerator | Frozen Block",
        )

        # Assert
        assert any("already in your inventory" in c for c in chunks)
        assert await _carried_count(db, avatar.id, "FROZEN_BLOCK") == 1


def test_detach_removes_the_item_from_override_and_row_contents() -> None:
    # Arrange
    crate = SimpleNamespace(id="CRATE", inventory=["KEY", {"id": "COIN"}])
    states = {"CRATE": {"locked": False}}

    # Act
    changed = detach_from_containers(states, [crate], ["key"])

    # Assert
    assert changed == ["CRATE"]
    assert states["CRATE"] == {"locked": False, "inventory": [{"id": "COIN"}]}
    assert crate.inventory == [{"id": "COIN"}]
