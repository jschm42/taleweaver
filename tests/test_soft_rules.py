"""Sequence-scoped soft rules: the GM judges the condition, Pass 1.5 validates and runs the script."""

import pytest
from sqlalchemy import select

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.api.routes.adventures.logic import AdventureLogic
from backend.core.script_validator import check_scripts_and_guards
from backend.engine.rules.rule_engine import GameEvent
from backend.engine.rules.soft_rules import (
    SoftRule,
    build_soft_rules_prompt_block,
    sequence_soft_rules,
)
from backend.engine.scripting.context import GameContext
from backend.models.world_entity import WorldEntity
from tests.conftest import TestSessionLocal
from tests.test_game_loop import _seed_game_context

BRENDA_RULES = [
    {
        "id": "BRENDA_ANGRY",
        "condition": "Arthur makes Brenda angry",
        "script": "tw.vars.set('BRENDA_TRUST', tw.vars.get('BRENDA_TRUST', 0) - 1)",
        "text": "Brenda's expression cools noticeably.",
    },
    {
        "id": "BRENDA_FLIRT",
        "condition": "Arthur flirts with Brenda",
        "guard_expression": "tw.vars.get('BRENDA_TRUST', 0) >= 0",
        "script": "tw.npcs.give_to_player('BRENDA', 'BRENDA_KEY')",
        "max_triggers": 1,
    },
]
SEQUENCES = [
    {"id": "SEQ_1_TAVERN", "order": 1, "title": "Tavern", "soft_rules": BRENDA_RULES},
    {"id": "SEQ_2_ROAD", "order": 2, "title": "Road", "soft_rules": []},
]


async def _manager(db, active_sequence_id: str = "SEQ_1_TAVERN") -> GameTurnManager:
    user, adv, _avatar, state = await _seed_game_context(db)
    adv.sequences = SEQUENCES
    state.active_sequence_id = active_sequence_id
    db.add_all([
        WorldEntity(id="BRENDA", session_id=state.session_id, entity_type="NPC", name="Brenda",
                    description="Innkeeper.", current_scene_id="START", inventory=["BRENDA_KEY"]),
        WorldEntity(id="BRENDA_KEY", session_id=state.session_id, entity_type="OBJECT",
                    name="Brenda's Key", description="A brass key.", item_type="KEY",
                    current_scene_id="START", is_hidden=True, is_in_inventory=True),
    ])  # fmt: skip
    await db.commit()
    manager = GameTurnManager(db, state.session_id, user)
    await manager.initialize()
    return manager


async def _fire(manager: GameTurnManager, *rule_ids: str) -> tuple[GameEvent, list[str]]:
    event = GameEvent(triggered_soft_rule_ids=list(rule_ids))
    sequence = AdventureLogic.resolve_active_sequence(manager.adventure, manager.state)
    messages = await manager.guardrails._enforce_soft_rules(event, sequence)
    return event, messages


def _trust(manager: GameTurnManager):
    return (manager.state.entity_states or {}).get("__script_vars__", {}).get("BRENDA_TRUST")


def _inventory_ids(manager: GameTurnManager) -> list[str]:
    return [item.get("id") for item in manager.avatar.inventory or []]


def test_prompt_block_lists_open_rules_without_scripts_or_guards():
    # Arrange
    rules = sequence_soft_rules({"soft_rules": [*BRENDA_RULES, {"id": "", "condition": "x"}]})

    # Act
    block = build_soft_rules_prompt_block(rules, {"BRENDA_FLIRT": 1})

    # Assert
    assert [rule.id for rule in rules] == ["BRENDA_ANGRY", "BRENDA_FLIRT"]
    assert "BRENDA_ANGRY" in block and "Arthur makes Brenda angry" in block
    assert "BRENDA_FLIRT" not in block  # exhausted rules are no longer offered
    assert "tw.vars" not in block and "give_item" not in block


def test_prompt_block_is_empty_without_open_rules():
    # Arrange
    rules = [SoftRule(id="ONCE", condition="c", max_triggers=1)]

    # Act
    block = build_soft_rules_prompt_block(rules, {"ONCE": 1})

    # Assert
    assert block == ""


@pytest.mark.asyncio
async def test_reported_rule_runs_script_and_shows_text(setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _manager(db)

        # Act
        event, messages = await _fire(manager, "BRENDA_ANGRY")

        # Assert
        assert event.triggered_soft_rule_ids == ["BRENDA_ANGRY"]
        assert _trust(manager) == -1
        assert "Brenda's expression cools noticeably." in messages


@pytest.mark.asyncio
async def test_guard_sees_effects_of_earlier_rule_in_same_message(setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _manager(db)

        # Act
        event, _messages = await _fire(manager, "BRENDA_ANGRY", "BRENDA_FLIRT")

        # Assert
        assert event.triggered_soft_rule_ids == ["BRENDA_ANGRY"]
        assert "BRENDA_KEY" not in _inventory_ids(manager)


@pytest.mark.asyncio
async def test_one_time_rule_fires_only_once(setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _manager(db)
        await _fire(manager, "BRENDA_FLIRT")

        # Act
        event, _messages = await _fire(manager, "BRENDA_FLIRT")

        # Assert
        assert event.triggered_soft_rule_ids is None
        assert _inventory_ids(manager).count("BRENDA_KEY") == 1


@pytest.mark.asyncio
async def test_rules_of_inactive_sequence_are_ignored(setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _manager(db, active_sequence_id="SEQ_2_ROAD")

        # Act
        event, messages = await _fire(manager, "BRENDA_ANGRY", "MADE_UP_RULE")

        # Assert
        assert event.triggered_soft_rule_ids is None
        assert messages == []
        assert _trust(manager) is None


def test_validator_reports_broken_soft_rule_script():
    # Arrange
    payload = {
        "sequences": [
            {"id": "SEQ_1", "soft_rules": [{"id": "BAD", "condition": "c", "script": "x = = 1"}]}
        ]
    }

    # Act
    findings = check_scripts_and_guards(payload)

    # Assert
    assert any((f.context or {}).get("soft_rule_id") == "BAD" for f in findings)


def _context_with_brenda(inventory: list) -> GameContext:
    entities = {
        "BRENDA": {"id": "BRENDA", "name": "Brenda", "entity_type": "NPC", "inventory": inventory},
        "BRENDA_KEY": {"id": "BRENDA_KEY", "name": "Brenda's Key", "entity_type": "OBJECT",
                       "description": "A brass key.", "item_type": "KEY"},
    }  # fmt: skip
    return GameContext(entities=entities, current_scene_id="START")


def test_npc_gives_carried_item_with_its_world_data():
    # Arrange
    tw = _context_with_brenda(["BRENDA_KEY"])

    # Act
    entry = tw.npcs.give_to_player("BRENDA", "brenda_key")

    # Assert
    assert entry == {"id": "BRENDA_KEY", "name": "Brenda's Key", "description": "A brass key.",
                     "item_type": "KEY"}  # fmt: skip
    assert tw.player.has_item("BRENDA_KEY")
    assert tw.npcs.get("BRENDA").inventory == []


def test_npc_cannot_give_item_it_does_not_carry():
    # Arrange
    tw = _context_with_brenda([])

    # Act
    entry = tw.npcs.give_to_player("BRENDA", "BRENDA_KEY")

    # Assert
    assert entry is None
    assert not tw.changeset.player_new_items
    assert not tw.changeset.entity_updates


@pytest.mark.asyncio
async def test_soft_rule_hand_over_persists_npc_and_item_state(setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _manager(db)

        # Act
        await _fire(manager, "BRENDA_FLIRT")

        # Assert
        rows = await db.execute(
            select(WorldEntity).where(WorldEntity.session_id == manager.state.session_id)
        )
        by_id = {row.id: row for row in rows.scalars().all()}
        assert _inventory_ids(manager) == ["BRENDA_KEY"]
        assert by_id["BRENDA"].inventory == []
        assert by_id["BRENDA_KEY"].is_in_inventory is True
        assert by_id["BRENDA_KEY"].is_hidden is False
        assert by_id["BRENDA_KEY"].current_scene_id == "INVENTORY"
