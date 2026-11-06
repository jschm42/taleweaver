"""Pass 1.5 guard against GM inventory removals the player's action does not account for."""

import pytest

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.api.routes.adventures.turn_pass_flow import run_guardrail_chain
from backend.engine.rules.rule_engine import GameEvent
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.session_state import SessionState
from backend.models.user import User

pytestmark = pytest.mark.asyncio

INVENTORY = [
    {"id": "TEST_SWORD", "name": "Practice Sword"},
    {"id": "HEALING_VIAL", "name": "Healing Vial"},
    {"id": "PET_ROCK", "name": "Googly-Eyed Pet Rock"},
]

ITEM_GIVEN_PROMPT = (
    "[ITEM_GIVEN] The player just gave Clockwork Self-Stirring Teacup to Bram Ironhand "
    "(ID BRAM). The engine already moved the item(s) into Bram Ironhand's inventory: do not "
    "add, remove or move them again."
)


@pytest.fixture
def small_llm_calls(monkeypatch):
    """Small-model reference check: 'potion' counts as a synonym of the Healing Vial."""
    from backend.core.llm_router import GameMasterLLM

    calls: list[str] = []
    monkeypatch.setattr(GameMasterLLM, "_get_decrypted_key", lambda self, provider: "dummy")

    async def fake_task(self, system_prompt, user_prompt, response_model, *args, **kwargs):
        calls.append(user_prompt)
        referenced = "HEALING_VIAL" in user_prompt and "potion" in user_prompt.lower()
        return response_model(referenced=referenced)

    monkeypatch.setattr(GameMasterLLM, "aexecute_complex_task", fake_task)
    return calls


async def _manager(db) -> GameTurnManager:
    user = User(username="player1", hashed_password="pw", role="user")
    adv = AdventureTemplate(id="adv-1", title="Test", owner_id="admin", time_per_turn=5)
    db.add_all([user, adv])
    await db.flush()
    avatar = Avatar(
        id="av-1",
        template_id=adv.id,
        user_id=user.id,
        name="Hero",
        role="Tester",
        hp=100,
        stats={},
        inventory=[dict(i) for i in INVENTORY],
    )
    db.add(avatar)
    await db.flush()
    state = SessionState(
        session_id="session-1",
        template_id=adv.id,
        avatar_id=avatar.id,
        user_id=user.id,
        current_scene_id="START",
        in_game_time=0,
    )
    db.add(state)
    await db.commit()
    manager = GameTurnManager(db, state.session_id, user)
    await manager.initialize()
    return manager


async def test_reaction_turn_after_give_keeps_unrelated_items(setup_test_db, small_llm_calls):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        manager = await _manager(db)
        event = GameEvent(removed_inventory_item_ids=["TEST_SWORD"])

        await manager.guardrails._enforce_inventory_removals(event, ITEM_GIVEN_PROMPT)

        assert event.removed_inventory_item_ids == []
        assert small_llm_calls == []


async def test_named_item_removal_is_kept_and_canonicalized(setup_test_db, small_llm_calls):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        manager = await _manager(db)
        event = GameEvent(removed_inventory_item_ids=["practice sword", "PET_ROCK"])

        await manager.guardrails._enforce_inventory_removals(
            event, "I drop the practice sword on the floor"
        )

        assert event.removed_inventory_item_ids == ["TEST_SWORD"]


async def test_synonym_removal_uses_small_model(setup_test_db, small_llm_calls):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        manager = await _manager(db)
        event = GameEvent(removed_inventory_item_ids=["HEALING_VIAL"])

        await manager.guardrails._enforce_inventory_removals(event, "I drink the potion")

        assert event.removed_inventory_item_ids == ["HEALING_VIAL"]
        assert len(small_llm_calls) == 1


async def test_removal_of_item_not_carried_is_dropped(setup_test_db, small_llm_calls):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        manager = await _manager(db)
        event = GameEvent(removed_inventory_item_ids=["GOLDEN_CROWN"])

        await manager.guardrails._enforce_inventory_removals(event, "I give the golden crown away")

        assert event.removed_inventory_item_ids == []


async def test_guardrail_chain_keeps_inventory_on_reaction_turn(setup_test_db, small_llm_calls):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        manager = await _manager(db)
        event = GameEvent(removed_inventory_item_ids=["TEST_SWORD"])
        violations: list[str] = []

        async for _ in run_guardrail_chain(manager, event, ITEM_GIVEN_PROMPT, violations):
            pass

        carried = {i["id"] for i in manager.avatar.inventory}
        assert "TEST_SWORD" in carried
        assert violations == []
