"""Giving items to NPCs: /give_items, typed "give X to Y" and the NPC's on_receive_item trigger."""

import pytest
from sqlalchemy import select

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.api.routes.adventures.npc_give import give_items_to_npc, typed_give_command
from backend.engine.interaction.command_parser import CommandParser
from backend.engine.rules.rule_engine import GameEvent
from backend.models.chat import ChatMessage
from backend.models.world_entity import WorldEntity
from tests.conftest import TestSessionLocal
from tests.test_game_loop import _seed_game_context

RECEIVE_SCRIPT = (
    "if 'SWORD' in received_item_ids:\n"
    "    tw.vars.set('armed', True)\n"
    "tw.vars.set('received_count', len(received_items))"
)


async def _seed_world(db) -> GameTurnManager:
    user, _adv, avatar, _state = await _seed_game_context(db)
    avatar.inventory = [{"id": "SWORD", "name": "Sword"}, {"id": "IRON_KEY", "name": "Iron Key"}]
    db.add_all(
        [
            WorldEntity(
                id="BRAM",
                session_id="session-1",
                entity_type="NPC",
                name="Bram Ironhand",
                description="A smith.",
                current_scene_id="START",
                hp=20,
                max_hp=20,
                metadata_json={
                    "on_receive_item_script": RECEIVE_SCRIPT,
                    "on_receive_item_text": "Bram weighs the gift in his hand.",
                },
            ),
            *(
                WorldEntity(
                    id=item_id,
                    session_id="session-1",
                    entity_type="OBJECT",
                    name=name,
                    description="Metal.",
                    current_scene_id="INVENTORY",
                    is_in_inventory=True,
                )
                for item_id, name in (("SWORD", "Sword"), ("IRON_KEY", "Iron Key"))
            ),
        ]
    )
    await db.commit()
    manager = GameTurnManager(db, "session-1", user)
    await manager.initialize()
    return manager


async def _row(db, entity_id: str) -> WorldEntity:
    res = await db.execute(select(WorldEntity).where(WorldEntity.id == entity_id))
    return res.scalars().first()


def test_give_items_command_maps_to_trigger_tag():
    # Act
    response = CommandParser.parse_command(None, "/give_items BRAM | SWORD")

    # Assert
    assert response == "[TRIGGER_GIVE_ITEMS] BRAM | SWORD"


@pytest.mark.asyncio
async def test_give_moves_items_to_npc_and_fires_trigger():
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _seed_world(db)

        # Act
        outcome = await give_items_to_npc(manager, "Bram Ironhand | Sword, Iron Key, Nothing")
        await db.commit()

        # Assert
        texts = [text for _role, text in outcome.events]
        assert texts[0] == "You give Sword, Iron Key to Bram Ironhand."
        assert texts[1] == "You don't carry Nothing."
        assert texts[-1] == "Bram weighs the gift in his hand."
        assert manager.avatar.inventory == []
        bram_state = manager.state.entity_states["BRAM"]
        assert [e["id"] for e in bram_state["inventory"]] == ["SWORD", "IRON_KEY"]
        script_vars = manager.state.entity_states["__script_vars__"]
        assert script_vars["armed"] is True
        assert script_vars["received_count"] == 2
        sword = await _row(db, "SWORD")
        assert (sword.current_scene_id, sword.is_hidden, sword.is_in_inventory) == (
            "INVENTORY",
            True,
            False,
        )
        assert "Bram Ironhand" in outcome.reaction_prompt
        rows = (await db.execute(select(ChatMessage.content))).scalars().all()
        assert "You give Sword, Iron Key to Bram Ironhand." in rows


@pytest.mark.asyncio
async def test_give_to_defeated_npc_is_refused():
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _seed_world(db)
        manager.state.entity_states = {"BRAM": {"is_defeated": True}}

        # Act
        outcome = await give_items_to_npc(manager, "BRAM | SWORD")

        # Assert
        assert outcome.events == [("system", "Bram Ironhand cannot take anything anymore.")]
        assert outcome.reaction_prompt is None
        assert [i["id"] for i in manager.avatar.inventory] == ["SWORD", "IRON_KEY"]


@pytest.mark.asyncio
async def test_give_without_carried_items_has_no_reaction():
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _seed_world(db)

        # Act
        outcome = await give_items_to_npc(manager, "BRAM | Golden Apple")

        # Assert
        assert outcome.events == [("system", "You don't carry Golden Apple.")]
        assert outcome.reaction_prompt is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("give the sword to Bram Ironhand", "/give_items BRAM | sword"),
        (
            "I give my Sword and the iron key to bram ironhand.",
            "/give_items BRAM | Sword, iron key",
        ),
        ("give a hug to Bram Ironhand", None),
        ("give the sword to the guard", None),
        ("look at the sword", None),
    ],
)
async def test_typed_give_becomes_command_only_for_real_handovers(message, expected):
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _seed_world(db)

        # Act
        command = await typed_give_command(manager, message)

        # Assert
        assert command == expected


@pytest.mark.asyncio
async def test_given_items_survive_the_following_gm_turn():
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _seed_world(db)
        await give_items_to_npc(manager, "BRAM | SWORD")

        # Act: the GM's reaction turn runs the inventory auto-sync of every turn
        await manager._apply_game_event(GameEvent(narrative_description="Bram nods."))

        # Assert
        assert [e["id"] for e in manager.state.entity_states["BRAM"]["inventory"]] == ["SWORD"]


@pytest.mark.asyncio
async def test_give_skips_gm_reaction_when_receive_script_opens_a_dialog():
    async with TestSessionLocal() as db:
        # Arrange: the NPC answers the handover with a question instead of a GM reaction
        manager = await _seed_world(db)
        bram = await _row(db, "BRAM")
        bram.metadata_json = {
            "on_receive_item_script": (
                "tw.dialog.choose('What do you want for it?', ['A deal', 'Nothing'], "
                "on_choice='on_bram_deal')"
            )
        }
        await db.commit()

        # Act
        outcome = await give_items_to_npc(manager, "BRAM | SWORD")

        # Assert
        assert outcome.reaction_prompt is None
        assert manager.state.entity_states["__pending_dialog__"]["prompt"] == (
            "What do you want for it?"
        )


@pytest.mark.asyncio
async def test_npc_line_of_the_receive_script_keeps_its_speech_role():
    async with TestSessionLocal() as db:
        # Arrange: Bram answers with tw.npcs.say, which is speech, not a system notice
        manager = await _seed_world(db)
        bram = await _row(db, "BRAM")
        bram.metadata_json = {
            "on_receive_item_script": "tw.npcs.say('BRAM', 'A fine blade, friend!')"
        }
        await db.commit()

        # Act
        outcome = await give_items_to_npc(manager, "Bram Ironhand | Sword")

        # Assert
        line = 'Bram Ironhand: "A fine blade, friend!"'
        assert ("assistant", line) in outcome.events
        assert ("system", line) not in outcome.events
