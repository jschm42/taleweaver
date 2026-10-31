"""Script item operations: clone, destroy, hide/reveal and transfers between holders."""

import pytest
from sqlalchemy import select

from backend.api.routes.adventures.container_put import put_items_into_container
from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.engine.interaction.trigger_service import TriggerService
from backend.engine.scripting.context import GameContext
from backend.engine.scripting.item_ops import DESTROYED_SCENE_ID
from backend.models.avatar import Avatar
from backend.models.chat import ChatMessage
from backend.models.world_entity import WorldEntity
from tests.conftest import TestSessionLocal
from tests.test_game_loop import _seed_game_context


def _entities() -> dict:
    return {
        "POTION": {
            "id": "POTION",
            "name": "Potion",
            "current_scene_id": "VAULT",
            "is_hidden": True,
        },
        "CHEST": {
            "id": "CHEST",
            "name": "Chest",
            "item_type": "CONTAINER",
            "current_scene_id": "START",
            "inventory": ["GEM"],
        },
        "GEM": {"id": "GEM", "name": "Gem", "current_scene_id": "START"},
        "SWORD": {"id": "SWORD", "name": "Sword", "current_scene_id": "INVENTORY"},
        "BOB": {"id": "BOB", "name": "Bob", "entity_type": "NPC", "current_scene_id": "START"},
    }


def _context() -> GameContext:
    return GameContext(
        avatar_data={"inventory": [{"id": "SWORD", "name": "Sword"}]},
        current_scene_id="START",
        entities=_entities(),
    )


def test_clone_gets_new_id_and_copies_place_and_hidden_flag():
    # Arrange
    context = _context()

    # Act
    first = context.objects.get("POTION").clone()
    second = context.objects.clone("POTION", scene_id="current", hidden=False)

    # Assert
    assert (first.id, first.current_scene_id, first.is_hidden) == ("POTION_1", "VAULT", True)
    assert (second.id, second.current_scene_id, second.is_hidden) == ("POTION_2", "START", False)
    assert [c["new_id"] for c in context.changeset.cloned_entities] == ["POTION_1", "POTION_2"]


def test_container_contents_and_take_to_npc():
    # Arrange
    context = _context()
    chest = context.objects.get("CHEST")

    # Act
    before = chest.item_ids
    moved = chest.take_item("GEM", to="BOB")

    # Assert
    assert before == ["GEM"]
    assert moved is True
    assert chest.item_ids == []
    assert context.npcs.get("BOB").item_ids == ["GEM"]
    assert context.objects.location("GEM") == {"type": "npc", "id": "BOB"}


def test_player_transfer_into_container_and_back():
    # Arrange
    context = _context()

    # Act
    stored = context.player.transfer_item("SWORD", "CHEST")
    contents = [i.id for i in context.objects.contents("CHEST")]
    taken = context.player.take_item("SWORD")

    # Assert
    assert stored is True
    assert contents == ["GEM", "SWORD"]
    assert taken is True
    assert context.player.item_ids == ["SWORD"]
    # Removing and re-adding the same item cancels out instead of duplicating it.
    assert context.changeset.player_new_items == []
    assert context.changeset.player_removed_item_ids == []


def test_destroy_detaches_and_marks_item():
    # Arrange
    context = _context()

    # Act
    context.objects.destroy("GEM")

    # Assert
    assert context.objects.get("CHEST").item_ids == []
    assert context.objects.location("GEM") == {"type": "destroyed", "id": ""}
    assert context.objects.get("GEM").is_destroyed is True


def test_hide_and_reveal_shortcuts():
    # Arrange
    context = _context()

    # Act
    context.objects.reveal("POTION")
    revealed = context.objects.get("POTION").is_hidden
    context.objects.get("POTION").hide()

    # Assert
    assert revealed is False
    assert context.objects.get("POTION").is_hidden is True


async def _seed_world(db) -> GameTurnManager:
    user, _adv, avatar, _state = await _seed_game_context(db)
    avatar.inventory = [{"id": "SWORD", "name": "Sword"}]
    rows = [
        WorldEntity(
            id="POTION",
            session_id="session-1",
            entity_type="OBJECT",
            name="Healing Potion",
            description="Red.",
            current_scene_id="VAULT",
            is_hidden=True,
            item_type="CONSUMABLE",
            metadata_json={"hp_change": 20},
        ),
        WorldEntity(
            id="ALTAR",
            session_id="session-1",
            entity_type="OBJECT",
            name="Altar",
            description="Stone.",
            current_scene_id="START",
            item_type="CONTAINER",
            is_portable=False,
            metadata_json={
                "on_items_added_script": (
                    "if 'SWORD' in added_item_ids:\n"
                    "    tw.vars.set('offered', True)\n"
                    "    tw.objects.get('POTION').clone(scene_id='current', hidden=False)"
                ),
                "on_items_added_text": "The altar hums.",
            },
        ),
        WorldEntity(
            id="SWORD",
            session_id="session-1",
            entity_type="OBJECT",
            name="Sword",
            description="Sharp.",
            current_scene_id="INVENTORY",
            is_in_inventory=True,
        ),
    ]
    db.add_all(rows)
    await db.commit()
    manager = GameTurnManager(db, "session-1", user)
    await manager.initialize()
    return manager


async def _row(db, entity_id: str) -> WorldEntity:
    res = await db.execute(select(WorldEntity).where(WorldEntity.id == entity_id))
    return res.scalars().first()


@pytest.mark.asyncio
async def test_clone_in_turn_script_creates_session_row():
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _seed_world(db)

        # Act
        await manager._execute_inline_script(
            "p = tw.objects.get('POTION').clone()\np.reveal()\np.move_to('player')",
            "on_interact",
            "DISPENSER",
        )
        await db.commit()

        # Assert
        clone = await _row(db, "POTION_1")
        assert clone is not None
        assert clone.name == "Healing Potion"
        assert clone.metadata_json == {"hp_change": 20}
        assert (clone.current_scene_id, clone.is_hidden, clone.is_in_inventory) == (
            "INVENTORY",
            False,
            True,
        )
        assert [i.get("id") for i in manager.avatar.inventory] == ["SWORD", "POTION_1"]
        assert (await _row(db, "POTION")).is_hidden is True


@pytest.mark.asyncio
async def test_trigger_script_moves_items_into_player_inventory():
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _seed_world(db)

        # Act
        await TriggerService.execute_trigger(
            db,
            manager.state,
            "on_exit_used",
            "EXIT",
            script_code="tw.player.take_item('POTION')\ntw.objects.destroy('SWORD')",
        )
        await db.commit()

        # Assert
        avatar = (await db.execute(select(Avatar).where(Avatar.id == "av-1"))).scalars().first()
        assert [i.get("id") for i in avatar.inventory] == ["POTION"]
        assert (await _row(db, "POTION")).is_in_inventory is True
        assert (await _row(db, "SWORD")).current_scene_id == DESTROYED_SCENE_ID


@pytest.mark.asyncio
async def test_put_items_stores_them_and_fires_trigger():
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _seed_world(db)

        # Act
        events = await put_items_into_container(manager.interactions, "ALTAR | Sword, Nothing")
        await db.commit()

        # Assert
        texts = [text for _role, text in events]
        assert texts[0] == "You put Sword into Altar."
        assert texts[1] == "You don't carry Nothing."
        assert texts[-1] == "The altar hums."
        assert manager.avatar.inventory == []
        altar_state = manager.state.entity_states["ALTAR"]
        assert [e["id"] for e in altar_state["inventory"]] == ["SWORD"]
        assert manager.state.entity_states["__script_vars__"]["offered"] is True
        assert (await _row(db, "POTION_1")).current_scene_id == "START"
        rows = (await db.execute(select(ChatMessage.content))).scalars().all()
        assert "You put Sword into Altar." in rows


@pytest.mark.asyncio
async def test_put_items_into_locked_container_is_refused():
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _seed_world(db)
        altar = await _row(db, "ALTAR")
        altar.metadata_json = {**altar.metadata_json, "locked": True, "code_to_unlock": "1234"}
        await db.commit()

        # Act
        events = await put_items_into_container(manager.interactions, "ALTAR | SWORD")

        # Assert
        assert events == [("system", "Altar is locked.")]
        assert [i.get("id") for i in manager.avatar.inventory] == ["SWORD"]
