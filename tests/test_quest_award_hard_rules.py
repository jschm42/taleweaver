"""Unit tests for Quest and Award Hard Rules (Deterministic Triggers & Scripting Guards)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.api.routes.adventures.turn_guardrails import (
    TurnGuardrailEnforcer,
)
from backend.api.routes.adventures.turn_state_applier import TurnStateApplier
from backend.engine.rules.hard_rule_evaluator import (
    HardRuleEvaluator,
    RuleEvaluationContext,
)
from backend.engine.rules.quest_manager import QuestManager
from backend.engine.rules.rule_engine import GameEvent
from backend.engine.world.world_schemas import (
    AwardTemplateSchema,
)
from backend.engine.world.world_schemas import (
    QuestSchema as ManifestQuestSchema,
)
from backend.schemas.adventure import AwardSchema, QuestSchema


def _setup_mock_manager():
    mock_manager = MagicMock()
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = []
    mock_res.scalars.return_value.first.return_value = MagicMock()
    mock_manager.db = MagicMock()
    mock_manager.db.execute = AsyncMock(return_value=mock_res)
    mock_manager.db.flush = AsyncMock()
    mock_manager.db.add = MagicMock()
    mock_manager.game_id = "test_game"
    mock_manager.state = MagicMock()
    mock_manager.state.session_id = "test_game"
    mock_manager.state.template_id = "test_adv"
    mock_manager.state.active_sequence_id = "SEQ_1"
    mock_manager.state.entity_states = {}
    mock_manager.state.current_scene_id = "START_ROOM"
    mock_manager.state.quests = []
    mock_manager.state.custom_variables = {}

    mock_manager.avatar = MagicMock()
    mock_manager.avatar.hp = 100
    mock_manager.avatar.inventory = []

    mock_manager.adventure = MagicMock()
    mock_manager.adventure.sequences = []
    mock_manager.adventure.quests = []
    mock_manager.adventure.awards = []

    mock_manager._save_chat_message = AsyncMock()
    mock_manager._collect_existing_item_ids = AsyncMock(return_value=set())
    mock_manager._apply_adventure_generator_tools = AsyncMock()
    mock_manager._queue_checkpoint = MagicMock()
    mock_manager._execute_inline_script = AsyncMock(return_value=[])

    return mock_manager


def test_quest_and_award_schema_hard_rules():
    """Verify schemas accept and default hard rule fields."""
    quest = QuestSchema(
        id="QUEST_1",
        title="Find the Relic",
        description="Search the catacombs",
        goal="Soft narrative goal",
        exp_reward=100,
        required_item_id="ANCIENT_RELIC",
        required_scene_id="CATACOMBS_DEEP",
        required_defeated_npc_id="LICH_LORD",
        guard_expression="tw.vars.get('relic_cleansed') == True",
    )
    assert quest.required_item_id == "ANCIENT_RELIC"
    assert quest.required_scene_id == "CATACOMBS_DEEP"
    assert quest.required_defeated_npc_id == "LICH_LORD"
    assert quest.guard_expression == "tw.vars.get('relic_cleansed') == True"

    award = AwardSchema(
        key="AWARD_1",
        title="Dungeon Delver",
        description="Explore every secret room",
        tier="bronze",
        requirement="Soft narrative requirement",
        required_item_id="SECRET_KEY",
        required_scene_id="HIDDEN_VAULT",
        required_defeated_npc_id="BOSS_SHADOW",
        guard_expression="tw.vars.get('secrets_found', 0) >= 3",
    )
    assert award.required_item_id == "SECRET_KEY"
    assert award.required_scene_id == "HIDDEN_VAULT"
    assert award.required_defeated_npc_id == "BOSS_SHADOW"
    assert award.guard_expression == "tw.vars.get('secrets_found', 0) >= 3"

    # Verify defaults
    manifest_quest = ManifestQuestSchema(
        id="Q2", title="Q2", description="Desc", goal="Goal", exp_reward=50, status="open"
    )
    assert manifest_quest.required_item_id == ""
    assert manifest_quest.required_scene_id == ""
    assert manifest_quest.required_defeated_npc_id == ""
    assert manifest_quest.guard_expression == ""

    manifest_award = AwardTemplateSchema(
        key="A2", title="A2", description="Desc", tier="bronze", requirement="Req"
    )
    assert manifest_award.required_item_id == ""
    assert manifest_award.required_scene_id == ""
    assert manifest_award.required_defeated_npc_id == ""
    assert manifest_award.guard_expression == ""


def test_hard_rule_evaluator_direct():
    """Verify HardRuleEvaluator correctly checks item, scene, NPC, and expression rules."""
    ctx = RuleEvaluationContext(
        current_scene_id="VAULT_ROOM",
        inventory_item_ids={"ANCIENT_KEY", "TORCH"},
        defeated_npc_ids={"GOBLIN_KING"},
        active_sequence_id="SEQ_1",
        custom_variables={"puzzle_solved": True},
    )

    # 1. Item rule: passes if item present
    rule_item = {"required_item_id": "ANCIENT_KEY"}
    assert HardRuleEvaluator.evaluate_target(rule_item, ctx) is True
    assert HardRuleEvaluator.is_rule_satisfied(rule_item, ctx) is True

    # 2. Item rule: fails if item absent
    rule_item_missing = {"required_item_id": "MAGIC_SWORD"}
    assert HardRuleEvaluator.evaluate_target(rule_item_missing, ctx) is False
    assert HardRuleEvaluator.is_rule_satisfied(rule_item_missing, ctx) is False

    # 3. Scene rule: passes if current scene matches
    rule_scene = {"required_scene_id": "VAULT_ROOM"}
    assert HardRuleEvaluator.evaluate_target(rule_scene, ctx) is True

    # 4. NPC rule: passes if NPC in defeated set
    rule_npc = {"required_defeated_npc_id": "GOBLIN_KING"}
    assert HardRuleEvaluator.evaluate_target(rule_npc, ctx) is True

    # 5. Guard expression rule: passes when Python expr is True
    rule_guard = {"guard_expression": "tw.vars.get('puzzle_solved') == True"}
    assert HardRuleEvaluator.evaluate_target(rule_guard, ctx) is True

    # 6. Guard expression rule: fails when Python expr is False
    rule_guard_fail = {"guard_expression": "tw.vars.get('puzzle_solved') == False"}
    assert HardRuleEvaluator.evaluate_target(rule_guard_fail, ctx) is False


def test_quest_manager_hard_rule_completion():
    """Verify QuestManager completes open quests when hard rules are satisfied."""
    avatar = MagicMock()
    avatar.inventory = [{"id": "SACRED_AMULET"}]
    state = MagicMock()
    state.quests = [
        {
            "id": "Q_FIND_AMULET",
            "title": "Find the Lost Amulet",
            "description": "Locate the sacred relic.",
            "status": "open",
            "required_item_id": "SACRED_AMULET",
        },
        {
            "id": "Q_DEFEAT_BEAST",
            "title": "Slay the Beast",
            "description": "Defeat the cave beast.",
            "status": "open",
            "required_defeated_npc_id": "CAVE_BEAST",
        },
    ]

    completed = QuestManager.evaluate_quests(
        avatar=avatar,
        state=state,
        new_inventory_items=[],
        new_scene_id="TUNNEL",
        updated_entities=[],
    )

    assert "Q_FIND_AMULET" in completed
    assert "Q_DEFEAT_BEAST" not in completed


@pytest.mark.asyncio
async def test_turn_state_applier_evaluates_deterministic_awards():
    """Verify TurnStateApplier evaluates unearned awards with hard rules."""
    manager = _setup_mock_manager()
    manager.user = MagicMock()
    manager.user.earned_awards = []
    manager.avatar.inventory = [{"id": "DRAGON_TOOTH"}]
    manager.adventure.awards = [
        {
            "key": "DRAGON_HUNTER",
            "title": "Dragon Hunter",
            "description": "Acquire a dragon tooth.",
            "tier": "bronze",
            "required_item_id": "DRAGON_TOOTH",
        },
        {
            "key": "MASTER_EXPLORER",
            "title": "Master Explorer",
            "description": "Enter the sanctum.",
            "tier": "bronze",
            "required_scene_id": "HIDDEN_SANCTUM",
        },
    ]

    applier = TurnStateApplier(manager)
    event = GameEvent(
        narrative_description="You pick up the dragon tooth.",
    )

    messages = await applier._evaluate_deterministic_awards(event)

    assert any("DRAGON_HUNTER" in msg or "Dragon Hunter" in msg for msg in messages)
    earned_keys = {ea.get("key") for ea in manager.user.earned_awards}
    assert "DRAGON_HUNTER" in earned_keys
    assert "MASTER_EXPLORER" not in earned_keys


@pytest.mark.asyncio
async def test_turn_guardrails_blocks_unmet_quest_hard_rules():
    """Verify TurnGuardrailEnforcer reverts quest completion if hard rules are unsatisfied."""
    manager = _setup_mock_manager()
    manager.state.quests = [
        {
            "id": "Q_BOSS",
            "title": "Defeat Overlord",
            "status": "open",
            "required_defeated_npc_id": "OVERLORD",
        }
    ]
    manager.state.entity_states = {}
    manager.state.current_scene_id = "THRONE_ROOM"
    manager.state.custom_variables = {}
    manager.avatar.inventory = []

    enforcer = TurnGuardrailEnforcer(manager)

    # LLM hallucinates quest completion without defeating OVERLORD
    game_event = GameEvent(
        narrative_description="The overlord runs away scared.",
        completed_quest_ids=["Q_BOSS"],
    )

    await enforcer._enforce_quest_and_award_guardrails(game_event)

    assert "Q_BOSS" not in (game_event.completed_quest_ids or [])


@pytest.mark.asyncio
async def test_turn_guardrails_blocks_unmet_award_hard_rules():
    """Verify TurnGuardrailEnforcer reverts award grant if hard rules are unsatisfied."""
    manager = _setup_mock_manager()
    manager.state.quests = []
    manager.state.entity_states = {}
    manager.state.current_scene_id = "GARDEN"
    manager.state.custom_variables = {"opened_treasure": False}
    manager.avatar.inventory = []
    manager.adventure.awards = [
        {
            "key": "TREASURE_MASTER",
            "title": "Treasure Master",
            "required_item_id": "ROYAL_CROWN",
            "guard_expression": "tw.vars.get('opened_treasure') == True",
        }
    ]

    enforcer = TurnGuardrailEnforcer(manager)

    # LLM hallucinates award grant without meeting hard rules
    game_event = GameEvent(
        narrative_description="You feel like a treasure master.",
        earned_award_keys=["TREASURE_MASTER"],
    )

    await enforcer._enforce_quest_and_award_guardrails(game_event)

    assert "TREASURE_MASTER" not in (game_event.earned_award_keys or [])
