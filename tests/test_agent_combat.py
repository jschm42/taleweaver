from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from backend.api.routes.adventures.agent_combat import (
    CombatSituation,
    ConsumableOption,
    choose_combat_action,
)
from backend.api.routes.adventures.agent_combat_math import (
    average_amount,
    expected_weapon_damage,
    weapon_hit_chances,
)

FIREBALL = {
    "id": "FIREBALL",
    "name": "Fireball",
    "cost_type": "mana",
    "cost": 30,
    "locked": False,
    "targets_enemy": True,
    "success_stat": "intelligence",
    "difficulty": None,
    "effects": [{"target": "target", "stat": "hp", "amount": "-4d10"}],
}
HEAL = {
    "id": "HEAL",
    "name": "Heal",
    "cost_type": "mana",
    "cost": 20,
    "locked": False,
    "targets_enemy": False,
    "success_stat": "wisdom",
    "difficulty": None,
    "effects": [{"target": "self", "stat": "hp", "amount": "+30"}],
}
SWORD = {"name": "Sword", "cost_type": "stamina", "cost": 20, "dice": "1d8"}


def _player(**overrides):
    player = {
        "hp": 100,
        "max_hp": 100,
        "mana": 100,
        "max_mana": 100,
        "stamina": 100,
        "max_stamina": 100,
        "ac": 10,
        "stats": {"dexterity": 10, "intelligence": 16, "wisdom": 12, "strength": 10},
        "modifiers": {},
        "special_actions": [],
    }
    player.update(overrides)
    return player


def _enemy(enemy_id, name, hp, ac=12):
    return {
        "id": enemy_id,
        "name": name,
        "hp": hp,
        "max_hp": 50,
        "ac": ac,
        "modifiers": {},
        "engaged": True,
        "defeated": False,
        "fled": False,
    }


def _situation(player=None, enemies=None, consumables=None, **combat_extra):
    combat = {"active": True, "enemies": enemies or [_enemy("ORC", "Orc", 40)], **combat_extra}
    return CombatSituation(
        combat=combat,
        player=player or _player(),
        weapon=dict(SWORD),
        consumables=consumables or [],
    )


def test_average_amount_handles_dice_and_flat_values():
    assert average_amount("1d8") == 4.5
    assert average_amount("-2d6+1") == -8.0
    assert average_amount("+5") == 5.0
    assert average_amount("garbage") == 0.0


def test_weapon_hit_chance_matches_engine_rules():
    # Arrange: dex 10 -> crit only on 20; needs d20 + 10 >= 15 -> 5..20 hit.
    player = _player()
    target = _enemy("A", "A", 10, ac=15)

    # Act
    hit, crit = weapon_hit_chances(player, target)

    # Assert
    assert hit == pytest.approx(16 / 20)
    assert crit == pytest.approx(1 / 20)
    assert expected_weapon_damage(player, target, SWORD) == pytest.approx(15 / 20 * 4.5 + 0.1 * 4.5)


def test_tactician_focuses_weakest_enemy_with_weapon():
    situation = _situation(enemies=[_enemy("ORC", "Orc", 40), _enemy("GOB", "Goblin", 5)])

    action, reason = choose_combat_action(situation)

    assert action == "Attack Goblin"
    assert "Goblin" in reason


def test_tactician_prefers_stronger_special_attack():
    situation = _situation(player=_player(special_actions=[FIREBALL]))

    action, _ = choose_combat_action(situation)

    assert action == "/special FIREBALL Orc"


def test_tactician_skips_locked_or_unaffordable_specials():
    locked = {**FIREBALL, "locked": True}
    situation = _situation(player=_player(mana=10, special_actions=[locked, HEAL]))

    action, _ = choose_combat_action(situation)

    assert action == "Attack Orc"


def test_tactician_heals_when_badly_wounded():
    potion = ConsumableOption(name="Healing Potion", deltas={"hp": 50, "mana": 0, "stamina": 0})
    situation = _situation(player=_player(hp=30, special_actions=[HEAL]), consumables=[potion])

    action, reason = choose_combat_action(situation)

    assert action == "/consume Healing Potion"
    assert "30%" in reason


def test_tactician_runs_when_dying_without_heal():
    situation = _situation(player=_player(hp=10, mana=0))

    action, _ = choose_combat_action(situation)

    assert action == "Run"


def test_tactician_rests_when_out_of_stamina():
    situation = _situation(player=_player(stamina=5, mana=0))

    action, _ = choose_combat_action(situation)

    assert action == "Rest"


def test_tactician_uses_enemy_id_for_duplicate_names():
    situation = _situation(enemies=[_enemy("GOB_1", "Goblin", 30), _enemy("GOB_2", "Goblin", 10)])

    action, _ = choose_combat_action(situation)

    assert action == "Attack GOB_2"


def test_tactician_runs_when_npcs_cannot_be_damaged():
    situation = _situation()
    situation.can_damage = False

    action, _ = choose_combat_action(situation)

    assert action == "Run"


def test_tactician_loots_everything_then_finishes():
    loot_items = [{"id": "SWORD_1", "name": "Rusty Sword"}]
    with_loot = _situation(active=False, loot_pending=True, loot_items=loot_items)
    with_loot.combat["active"] = False
    empty = _situation(loot_pending=True, loot_items=[])
    empty.combat["active"] = False

    assert choose_combat_action(with_loot)[0] == "/loot take SWORD_1"
    assert choose_combat_action(empty)[0] == "/loot done"


@pytest.mark.asyncio
async def test_decide_uses_tactician_during_combat_without_llm():
    from backend.api.routes.adventures.agent_logic import AgentDecision
    from backend.api.routes.adventures.agent_turn_stream import _decide

    manager = SimpleNamespace(_has_combat_phase=lambda: True)
    tactical = AgentDecision(
        thoughts="[Combat tactician] x", action="Rest", is_stuck_or_bug=False, issue_description=""
    )
    with (
        patch(
            "backend.api.routes.adventures.agent_turn_stream.decide_combat_turn",
            AsyncMock(return_value=tactical),
        ),
        patch(
            "backend.api.routes.adventures.agent_turn_stream.AgentService.get_decision",
            AsyncMock(),
        ) as llm_decision,
    ):
        decision, failed = await _decide(None, "game", None, manager)

    assert decision.action == "Rest"
    assert failed is False
    llm_decision.assert_not_called()


@pytest.mark.asyncio
async def test_tactician_plays_a_real_fight_round(setup_test_db, monkeypatch):
    import copy
    from unittest.mock import MagicMock

    from backend.api.routes.adventures.agent_combat import decide_combat_turn
    from backend.api.routes.adventures.combat.player_actions import INVALID_ACTION_MSG
    from backend.api.routes.adventures.gameplay_logic import GameTurnManager
    from backend.engine.rule_engine import GameEvent
    from tests.conftest import TestSessionLocal
    from tests.test_combat_specials import _seed_combat_context

    # Arrange
    async with TestSessionLocal() as db:
        user, *_ = await _seed_combat_context(db)
        mock_llm = MagicMock()
        mock_llm.aexecute_complex_task = AsyncMock(
            return_value=GameEvent(narrative_description="Fight progresses.")
        )

        async def mock_stream(*args, **kwargs):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="Round continues."))])

        mock_llm.stream_simple_task = AsyncMock(return_value=mock_stream())
        monkeypatch.setattr(
            "backend.api.routes.adventures.gameplay_logic.GameMasterLLM",
            lambda *args, **kwargs: mock_llm,
        )
        manager = GameTurnManager(db, "session-combat", user)
        async for _ in manager.process_turn("/fight GOBLIN"):
            pass
        combat_before = copy.deepcopy(manager._read_combat_state())

        # Act
        decision = await decide_combat_turn(manager)
        assert manager._read_combat_state() == combat_before
        chunks = [chunk async for chunk in manager.process_turn(decision.action)]

    # Assert
    assert decision.action == "Attack Goblin"
    assert decision.thoughts.startswith("[Combat tactician]")
    assert not any(INVALID_ACTION_MSG in chunk for chunk in chunks)
