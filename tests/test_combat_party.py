"""The companion in turn-based combat: party side, its turn, enemy targeting, downed state."""

import pytest

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.engine.party.party_state import PARTY_KEY
from backend.models.world_entity import WorldEntity
from tests.conftest import TestSessionLocal
from tests.test_combat_encounters import LETHAL, MISS, SESSION_ID, _patch_dice, _play, _seed

pytestmark = pytest.mark.asyncio


async def _seed_with_companion(db, tactics="BALANCED"):
    user, avatar, state = await _seed(db)
    db.add(
        WorldEntity(
            id="BATLIN",
            session_id=SESSION_ID,
            entity_type="NPC",
            name="Batlin",
            description="A loyal servant in a bat costume.",
            current_scene_id="ARENA",
            hp=20,
            max_hp=20,
            is_hidden=False,
            is_in_inventory=False,
            metadata_json={"companion": {"tactics": tactics, "downed_recovery": 0.5}},
        )
    )
    state.entity_states = {PARTY_KEY: {"active_id": "BATLIN", "recruited": ["BATLIN"]}}
    await db.commit()
    return user, avatar, state


async def test_companion_fights_on_the_party_side(setup_test_db, monkeypatch):
    async with TestSessionLocal() as db:
        # Arrange
        user, _avatar, _state = await _seed_with_companion(db)
        _patch_dice(monkeypatch)
        manager = GameTurnManager(db, SESSION_ID, user)

        # Act
        await _play(manager, "/fight GOBLIN")

        # Assert: Batlin is no enemy or bystander, but a party member with an initiative slot
        combat = manager._read_combat_state()
        assert "BATLIN" not in [e["id"] for e in combat["enemies"]]
        assert [m["id"] for m in combat["party"]] == ["BATLIN"]
        assert "BATLIN" in [e["id"] for e in combat["initiative"]]


async def test_player_cannot_start_a_fight_against_the_companion(setup_test_db, monkeypatch):
    async with TestSessionLocal() as db:
        # Arrange
        user, _avatar, _state = await _seed_with_companion(db)
        _patch_dice(monkeypatch)
        manager = GameTurnManager(db, SESSION_ID, user)

        # Act
        chunks = await _play(manager, "/fight Batlin")

        # Assert
        assert any("is your companion" in chunk for chunk in chunks)
        assert not manager._read_combat_state().get("active")


async def test_offensive_companion_attacks_the_weakest_enemy(setup_test_db, monkeypatch):
    async with TestSessionLocal() as db:
        # Arrange: Goblin and Orc both engaged, the Orc is weaker
        user, _avatar, _state = await _seed_with_companion(db, tactics="OFFENSIVE")
        _patch_dice(monkeypatch)
        manager = GameTurnManager(db, SESSION_ID, user)
        await _play(manager, "/fight GOBLIN")
        combat = manager._read_combat_state()
        for enemy in combat["enemies"]:
            enemy["engaged"] = True
        next(e for e in combat["enemies"] if e["id"] == "ORC")["hp"] = 5
        monkeypatch.setattr(
            "backend.api.routes.adventures.gameplay_logic.roll_attack",
            lambda *_a, **_k: dict(LETHAL),
        )

        # Act
        _ = [c async for c in manager.combat._resolve_companion_turn("BATLIN", combat)]

        # Assert: the Orc is down, the Goblin untouched, the fight goes on
        orc = next(e for e in combat["enemies"] if e["id"] == "ORC")
        goblin = next(e for e in combat["enemies"] if e["id"] == "GOBLIN")
        assert orc["defeated"] is True
        assert goblin["hp"] == 30
        assert combat["active"] is True
        actions = [e for e in combat["log"] if e.get("type") == "party_action"]
        assert actions and actions[-1]["data"]["actor"] == "BATLIN"
        assert actions[-1]["data"]["target"] == "ORC"


async def test_enemy_hit_downs_the_companion_and_victory_revives_it(setup_test_db, monkeypatch):
    async with TestSessionLocal() as db:
        # Arrange
        user, _avatar, _state = await _seed_with_companion(db)
        _patch_dice(monkeypatch)
        manager = GameTurnManager(db, SESSION_ID, user)
        await _play(manager, "/fight GOBLIN")
        combat = manager._read_combat_state()
        member = combat["party"][0]
        goblin = next(e for e in combat["enemies"] if e["id"] == "GOBLIN")
        monkeypatch.setattr(
            "backend.api.routes.adventures.gameplay_logic.roll_attack",
            lambda *_a, **_k: dict(LETHAL),
        )
        weapon = {"name": "claws", "hit_stat": "strength", "dice": "1d6", "category": "MELEE"}

        # Act: a lethal hit on Batlin, then the fight is won
        text, _data = manager.combat._enemy_attacks_member(goblin, member, weapon, combat)
        downed = dict(member)
        can_act_while_downed = manager.combat._party_can_act(combat, "BATLIN")
        for enemy in combat["enemies"]:
            enemy["hp"] = 0
            enemy["defeated"] = True
        manager.combat._check_victory(combat)

        # Assert: downed during the fight (no initiative turn), back on its feet afterwards
        assert "is downed" in text
        assert downed["downed"] is True and downed["hp"] == 0
        assert can_act_while_downed is False
        assert member["downed"] is False
        assert member["hp"] == 10  # downed_recovery 0.5 of 20
        assert manager.state.entity_states["BATLIN"]["hp"] == 10


async def test_enemies_mostly_attack_the_protagonist(setup_test_db, monkeypatch):
    async with TestSessionLocal() as db:
        # Arrange: random() = 1.0 never picks the companion
        user, _avatar, _state = await _seed_with_companion(db)
        _patch_dice(monkeypatch, MISS)
        manager = GameTurnManager(db, SESSION_ID, user)
        await _play(manager, "/fight GOBLIN")
        combat = manager._read_combat_state()

        # Act
        target = manager.combat._enemy_target_member(combat)
        monkeypatch.setattr(
            "backend.api.routes.adventures.gameplay_logic.random.random", lambda: 0.0
        )
        drawn = manager.combat._enemy_target_member(combat)

        # Assert
        assert target is None
        assert drawn["id"] == "BATLIN"


async def test_attack_log_names_the_weapon_and_the_target():
    # Arrange
    from backend.api.routes.adventures.combat.attacks import attack_log_text

    roll = {**LETHAL, "hit_modifier": 2, "damage_dice_str": "1d8"}

    # Act
    text = attack_log_text("Batlin", roll, 12, "Practice Sword", "Goblin")
    plain = attack_log_text("Batlin", roll, 12)

    # Assert
    assert text.startswith("Batlin attacks Goblin with Practice Sword: ATTACK ROLL: 19 + 2")
    assert plain.startswith("Batlin ATTACK ROLL:")
