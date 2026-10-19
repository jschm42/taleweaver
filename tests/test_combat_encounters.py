"""Integration tests for multi-enemy encounters, initiative and special attacks."""

import pytest

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity

pytestmark = pytest.mark.asyncio

SESSION_ID = "session-encounter"
MISS = {
    "hit_roll": 2, "hit_modifier": 0, "hit_total": 2, "target_ac": 10, "is_hit": False,
    "damage_total": 0, "damage_dice_total": 0, "damage_rolls": [], "damage_bonus": 0,
    "damage_dice_str": "1d6",
}  # fmt: skip
LETHAL = {
    **MISS,
    "hit_roll": 19,
    "hit_total": 25,
    "is_hit": True,
    "damage_total": 99,
    "damage_rolls": [99],
}


def _npc(npc_id: str, name: str, **extra) -> WorldEntity:
    return WorldEntity(
        id=npc_id,
        session_id=SESSION_ID,
        entity_type="NPC",
        name=name,
        description=f"A {name}.",
        current_scene_id="ARENA",
        hp=30,
        max_hp=30,
        stat_modifier_dexterity=2,
        is_hidden=False,
        is_in_inventory=False,
        **extra,
    )


async def _seed(db, special_actions=None):
    user = User(username="encounter_tester", hashed_password="pw", role="user")
    adv = AdventureTemplate(
        id="adv-enc",
        title="Arena",
        owner_id="admin",
        time_per_turn=5,
        strict_rules=True,
        rule_enforcement_mode="rpg",
    )
    db.add_all([user, adv])
    await db.flush()
    avatar = Avatar(
        id="av-enc", template_id=adv.id, user_id=user.id, name="Hero", role="Bard",
        hp=100, max_hp=100, mana=50, max_mana=50, stamina=100, max_stamina=100,
        stats={"special_actions": special_actions or [],
               "unlocked_actions": [a["id"] for a in special_actions or []]},
        inventory=[], equipment={},
    )  # fmt: skip
    db.add(avatar)
    state = SessionState(
        session_id=SESSION_ID,
        template_id=adv.id,
        avatar_id=avatar.id,
        user_id=user.id,
        current_scene_id="ARENA",
        in_game_time=0,
        entity_states={},
    )
    db.add(state)
    db.add_all([
        _npc("GOBLIN", "Goblin", inventory=[{"id": "DAGGER", "name": "Dagger"}]),
        _npc("ORC", "Orc", inventory=[{"id": "AXE", "name": "Axe"}]),
        _npc("MERCHANT", "Merchant", is_attackable=False),
    ])  # fmt: skip
    await db.commit()
    return user, avatar, state


def _patch_dice(monkeypatch, roll=MISS):
    monkeypatch.setattr(
        "backend.api.routes.adventures.gameplay_logic.random.randint", lambda *_a, **_k: 20
    )
    monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.random.random", lambda: 1.0)
    monkeypatch.setattr(
        "backend.api.routes.adventures.gameplay_logic.roll_attack", lambda *_a, **_k: dict(roll)
    )


async def _play(manager, command):
    return [chunk async for chunk in manager.process_turn(command)]


async def test_fight_builds_card_stack_with_attackable_npcs_only(setup_test_db, monkeypatch):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        # Arrange
        user, _avatar, _state = await _seed(db)
        _patch_dice(monkeypatch)
        manager = GameTurnManager(db, SESSION_ID, user)

        # Act
        await _play(manager, "/fight GOBLIN")

        # Assert
        combat = manager._read_combat_state()
        ids = [e["id"] for e in combat["enemies"]]
        assert ids == ["GOBLIN", "ORC"]
        assert combat["enemies"][0]["engaged"] is True
        assert combat["enemies"][1]["engaged"] is False
        assert [e["id"] for e in combat["initiative"]] == ["PLAYER", "GOBLIN"]
        assert combat["turn"] == "player"
        assert combat["enemy"]["id"] == "GOBLIN"


async def test_attacking_passive_npc_engages_it_for_next_round(setup_test_db, monkeypatch):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        # Arrange
        user, _avatar, _state = await _seed(db)
        _patch_dice(monkeypatch)
        manager = GameTurnManager(db, SESSION_ID, user)
        await _play(manager, "/fight GOBLIN")

        # Act
        await _play(manager, "/attack ORC")

        # Assert
        combat = manager._read_combat_state()
        orc = next(e for e in combat["enemies"] if e["id"] == "ORC")
        assert orc["engaged"] is True
        assert combat["round"] == 2
        assert {e["id"] for e in combat["initiative"]} == {"PLAYER", "GOBLIN", "ORC"}
        assert combat["log"][-1]["type"] == "turn"


async def test_victory_requires_all_engaged_enemies_and_merges_loot(setup_test_db, monkeypatch):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        # Arrange
        user, _avatar, _state = await _seed(db)
        _patch_dice(monkeypatch)
        manager = GameTurnManager(db, SESSION_ID, user)
        await _play(manager, "/fight GOBLIN")
        await _play(manager, "/attack ORC")
        monkeypatch.setattr(
            "backend.api.routes.adventures.gameplay_logic.roll_attack",
            lambda *_a, **_k: dict(LETHAL),
        )

        # Act
        await _play(manager, "/attack GOBLIN")
        mid_fight = dict(manager._read_combat_state())
        await _play(manager, "/attack ORC")

        # Assert
        assert mid_fight["active"] is True
        combat = manager._read_combat_state()
        assert combat["active"] is False
        assert combat["outcome"] == "victory"
        assert {i["id"] for i in combat["loot_items"]} == {"DAGGER", "AXE"}


async def test_player_special_attack_rolls_and_applies_effects(setup_test_db, monkeypatch):
    from tests.conftest import TestSessionLocal

    insult = {
        "id": "INSULT", "name": "Your Mother Was a Hamster", "description": "Hurts feelings.",
        "action_type": "UTILITY", "category": "SOCIAL", "cost_type": "stamina", "cost": 15,
        "effects": [{"target": "target", "stat": "hp", "amount": "-7"},
                    {"target": "target", "stat": "dexterity", "amount": "-2"}],
    }  # fmt: skip
    async with TestSessionLocal() as db:
        # Arrange
        user, avatar, _state = await _seed(db, special_actions=[insult])
        _patch_dice(monkeypatch)
        monkeypatch.setattr("backend.engine.combat.special_attacks.random.randint", lambda *_a: 18)
        manager = GameTurnManager(db, SESSION_ID, user)
        await _play(manager, "/fight GOBLIN")

        # Act
        await _play(manager, "/special INSULT GOBLIN")

        # Assert
        combat = manager._read_combat_state()
        goblin = next(e for e in combat["enemies"] if e["id"] == "GOBLIN")
        special_log = next(
            e for e in combat["log"] if (e.get("data") or {}).get("kind") == "special"
        )
        assert goblin["hp"] == 23
        assert goblin["modifiers"]["dexterity"] == -2
        assert avatar.stamina == 85
        assert special_log["data"]["success"] is True
        assert (manager.state.entity_states or {})["GOBLIN"]["hp"] == 23


async def test_npc_special_attack_can_drain_player(setup_test_db, monkeypatch):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        # Arrange
        user, avatar, state = await _seed(db)
        goblin = await manager_entity(db, "GOBLIN")
        goblin.mana = 30
        goblin.max_mana = 30
        goblin.metadata_json = {"special_actions": [{
            "id": "SAP", "name": "Life Sap", "action_type": "ATTACK", "cost": 10,
            "effects": [{"target": "target", "stat": "hp", "amount": "-12"},
                        {"target": "self", "stat": "hp", "amount": "+5"}],
        }]}  # fmt: skip
        await db.commit()
        _patch_dice(monkeypatch)
        monkeypatch.setattr(
            "backend.api.routes.adventures.gameplay_logic.random.random", lambda: 0.0
        )
        monkeypatch.setattr("backend.engine.combat.special_attacks.random.randint", lambda *_a: 19)
        manager = GameTurnManager(db, SESSION_ID, user)
        await _play(manager, "/fight GOBLIN")

        # Act
        await _play(manager, "/rest")

        # Assert
        combat = manager._read_combat_state()
        assert avatar.hp == 88
        assert combat["enemies"][0]["mana"] == 20
        assert any("Life Sap" in e["text"] for e in combat["log"] if e["type"] == "enemy_action")


async def manager_entity(db, entity_id):
    from sqlalchemy import select

    res = await db.execute(
        select(WorldEntity).where(WorldEntity.id == entity_id, WorldEntity.session_id == SESSION_ID)
    )
    return res.scalars().first()


async def test_debug_win_fight_defeats_all_engaged_enemies(setup_test_db, monkeypatch):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        # Arrange
        user, _avatar, _state = await _seed(db)
        _patch_dice(monkeypatch)
        manager = GameTurnManager(db, SESSION_ID, user)
        await _play(manager, "/fight GOBLIN")
        await _play(manager, "/attack ORC")

        # Act
        await _play(manager, "/debug win_fight")

        # Assert
        combat = manager._read_combat_state()
        assert combat["outcome"] == "victory"
        assert combat["loot_pending"] is True
        assert all(e["defeated"] for e in combat["enemies"] if e["engaged"])
        assert {i["id"] for i in combat["loot_items"]} == {"DAGGER", "AXE"}
