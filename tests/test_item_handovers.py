"""Pass 1 handovers (`given_items`): validated in Pass 1.5, then performed with the receive trigger.

Regression: "/say Here is your drink, Tina" let the GM remove the drink, so it vanished and
Tina's on_receive_item script never ran.
"""

import pytest

from backend.api.routes.adventures.handover_flow import apply_item_handovers
from backend.api.routes.adventures.turn_pass_flow import run_guardrail_chain
from backend.engine.rules.rule_engine import GameEvent
from tests.conftest import TestSessionLocal
from tests.test_npc_give import _seed_world

SAY_HANDOVER = "/say Here, Bram, take my sword and keep it safe!"
# What the fake small model answers to the handover check (tests set it).
HANDOVER_ANSWER: list[dict] = []


@pytest.fixture(autouse=True)
def small_llm_calls(monkeypatch):
    """Small-model reference check without network: only the sword counts as referenced."""
    from backend.core.llm_router import GameMasterLLM

    calls: list[str] = []
    monkeypatch.setattr(GameMasterLLM, "_get_decrypted_key", lambda self, provider: "dummy")

    async def fake_task(self, system_prompt, user_prompt, response_model, *args, **kwargs):
        calls.append(user_prompt)
        if response_model.__name__ == "HandoverCheckResponse":
            return response_model(handovers=HANDOVER_ANSWER)
        return response_model(referenced=False)

    monkeypatch.setattr(GameMasterLLM, "aexecute_complex_task", fake_task)
    return calls


async def _guard(manager, event: GameEvent, user_msg: str) -> GameEvent:
    violations: list[str] = []
    async for _chunk in run_guardrail_chain(manager, event, user_msg, violations):
        pass
    assert violations == []
    return event


def _handover(item: str, npc: str) -> dict:
    return {"item_id": item, "npc_id": npc}


@pytest.mark.asyncio
async def test_dialogue_handover_moves_item_and_fires_receive_trigger():
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _seed_world(db)
        event = GameEvent(
            given_items=[_handover("Sword", "Bram Ironhand")],
            removed_inventory_item_ids=["SWORD"],
        )

        # Act
        await _guard(manager, event, SAY_HANDOVER)
        chunks = [chunk async for chunk in apply_item_handovers(manager, event)]

        # Assert
        assert [(h.item_id, h.npc_id) for h in event.given_items] == [("SWORD", "BRAM")]
        assert (
            event.removed_inventory_item_ids == []
        )  # the engine moves it, the GM does not remove it
        assert [i["id"] for i in manager.avatar.inventory] == ["IRON_KEY"]
        bram_inventory = manager.state.entity_states["BRAM"]["inventory"]
        assert [i["id"] for i in bram_inventory] == ["SWORD"]
        assert manager.state.entity_states["__script_vars__"]["armed"] is True
        assert any("You give Sword to Bram Ironhand." in c for c in chunks)
        assert any("Bram weighs the gift in his hand." in c for c in chunks)


@pytest.mark.asyncio
async def test_handover_needs_a_carried_item_the_player_refers_to(small_llm_calls):
    async with TestSessionLocal() as db:
        manager = await _seed_world(db)
        event = GameEvent(
            given_items=[
                _handover("IRON_KEY", "BRAM"),  # carried, but the message is about the sword
                _handover("GOLD_CROWN", "BRAM"),  # not carried
                _handover("SWORD", "BRAM"),
                _handover("SWORD", "BRAM"),  # duplicate
            ]
        )

        await _guard(manager, event, SAY_HANDOVER)

        assert [(h.item_id, h.npc_id) for h in event.given_items] == [("SWORD", "BRAM")]
        # The iron key was not named: the small model was asked (synonym/translation check).
        assert any("IRON_KEY" in call for call in small_llm_calls)


@pytest.mark.asyncio
async def test_handover_to_someone_not_here_keeps_the_item():
    async with TestSessionLocal() as db:
        manager = await _seed_world(db)
        event = GameEvent(given_items=[_handover("SWORD", "GHOST")])

        await _guard(manager, event, "/say Ghost, take my sword!")
        chunks = [chunk async for chunk in apply_item_handovers(manager, event)]

        assert event.given_items == []
        assert chunks == []
        assert [i["id"] for i in manager.avatar.inventory] == ["SWORD", "IRON_KEY"]


@pytest.mark.asyncio
async def test_engine_reaction_and_arrival_turns_never_hand_items_over():
    async with TestSessionLocal() as db:
        manager = await _seed_world(db)
        reaction = GameEvent(given_items=[_handover("SWORD", "BRAM")])
        await _guard(manager, reaction, "[ITEM_GIVEN] The player just gave Sword to Bram.")

        manager.arrival_narration = True
        arrival = GameEvent(given_items=[_handover("SWORD", "BRAM")])
        await _guard(manager, arrival, SAY_HANDOVER)

        assert reaction.given_items == []
        assert arrival.given_items == []


def test_pass1_schema_offers_given_items():
    from backend.engine.interaction.llm_intents import MechanicsIntent

    assert "given_items" in MechanicsIntent.model_fields


DEAL_SCRIPT = (
    "tw.dialog.choose('Pink Glitter Zero?! What do you want for it?', "
    "['Scream for Mom!', 'Nothing, it is a gift.'], on_choice='on_deal', speaker='Bram')"
)


@pytest.mark.asyncio
async def test_receive_dialog_opens_and_recipient_skips_on_interact():
    from backend.api.routes.adventures.dialog_narration import open_choice_reminder
    from backend.api.routes.adventures.handover_flow import handover_recipients
    from backend.engine.scripting.dialog import pending_dialog

    async with TestSessionLocal() as db:
        # Arrange: the receive trigger asks the player what the deal is.
        manager = await _seed_world(db)
        bram = await manager._find_scene_npc_by_hint("BRAM")
        bram.metadata_json = {**bram.metadata_json, "on_receive_item_script": DEAL_SCRIPT}
        event = GameEvent(given_items=[_handover("SWORD", "BRAM")])

        # Act
        await _guard(manager, event, SAY_HANDOVER)
        _chunks = [chunk async for chunk in apply_item_handovers(manager, event)]
        dialog = pending_dialog(manager.state.entity_states)
        reminder = open_choice_reminder(manager.state.entity_states)

    # Assert
    assert handover_recipients(event) == {"BRAM"}  # no on_interact for Bram this turn
    assert dialog["prompt"].startswith("Pink Glitter Zero?!")
    assert "OPEN CHOICE (Bram asks)" in reminder
    assert '"Scream for Mom!"' in reminder
    assert "do not choose for the player" in reminder


def test_no_reminder_without_open_choice():
    from backend.api.routes.adventures.dialog_narration import open_choice_reminder

    assert open_choice_reminder({}) is None
    assert open_choice_reminder(None) is None


@pytest.mark.asyncio
async def test_removal_that_was_a_handover_is_recovered(monkeypatch, small_llm_calls):
    # Arrange: Pass 1 booked the handover as a plain removal (no given_items).
    monkeypatch.setattr(
        "tests.test_item_handovers.HANDOVER_ANSWER", [{"item_id": "SWORD", "npc_id": "BRAM"}]
    )
    async with TestSessionLocal() as db:
        manager = await _seed_world(db)
        event = GameEvent(
            narrative_description="Bram snatches the sword.", removed_inventory_item_ids=["SWORD"]
        )

        # Act
        await _guard(manager, event, SAY_HANDOVER)
        chunks = [chunk async for chunk in apply_item_handovers(manager, event)]

        # Assert
        assert [(h.item_id, h.npc_id) for h in event.given_items] == [("SWORD", "BRAM")]
        assert event.removed_inventory_item_ids == []
        assert any("Bram weighs the gift in his hand." in c for c in chunks)
        assert any("Bram snatches the sword." in call for call in small_llm_calls)


@pytest.mark.asyncio
async def test_removal_stays_when_it_was_no_handover(monkeypatch, small_llm_calls):
    monkeypatch.setattr("tests.test_item_handovers.HANDOVER_ANSWER", [])
    async with TestSessionLocal() as db:
        manager = await _seed_world(db)
        event = GameEvent(removed_inventory_item_ids=["SWORD"])

        await _guard(manager, event, "/say I throw my sword into the river.")

        assert event.given_items in (None, [])
        assert event.removed_inventory_item_ids == ["SWORD"]


@pytest.mark.asyncio
async def test_no_handover_check_without_characters(small_llm_calls):
    async with TestSessionLocal() as db:
        manager = await _seed_world(db)
        bram = await manager._find_scene_npc_by_hint("BRAM")
        bram.current_scene_id = "ELSEWHERE"
        await db.flush()
        event = GameEvent(removed_inventory_item_ids=["SWORD"])

        await _guard(manager, event, SAY_HANDOVER)

        assert event.removed_inventory_item_ids == ["SWORD"]
        assert not any("Removed items" in call for call in small_llm_calls)
