"""Tests for cloning NPCs from scripts (tw.npcs.clone) and fighting a cloned pack."""

import pytest
from sqlalchemy import select

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.engine.scripting.context import GameContext
from backend.engine.scripting.runner import ScriptRunner
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity
from tests.conftest import TestSessionLocal

SESSION_ID = "session-clone"
MISS = {
    "hit_roll": 2, "hit_modifier": 0, "hit_total": 2, "target_ac": 10, "is_hit": False,
    "damage_total": 0, "damage_dice_total": 0, "damage_rolls": [], "damage_bonus": 0,
    "damage_dice_str": "1d6",
}  # fmt: skip


def _run(code: str, entities: dict) -> GameContext:
    context = GameContext(current_scene_id="PIT", entities=entities)
    ScriptRunner([]).execute_code(code, {"tw": context, "game": context})
    return context


def _rat_data(**extra) -> dict:
    return {"id": "RAT", "name": "Rat", "entity_type": "NPC", "current_scene_id": "PIT",
            "hp": 1, "max_hp": 3, "is_hidden": True, "is_defeated": True,
            "inventory": [{"id": "CHEESE"}], **extra}  # fmt: skip


def test_clone_creates_fresh_npc_with_new_ids():
    # Act
    context = _run(
        "for i in range(3):\n    tw.npcs.clone('RAT', hidden=False)", {"RAT": _rat_data()}
    )

    # Assert
    clones = context.changeset.cloned_entities
    assert [c["new_id"] for c in clones] == ["RAT_1", "RAT_2", "RAT_3"]
    assert all(c["fresh_npc"] and not c["is_hidden"] for c in clones)
    rat = context.npcs.get("RAT_2")
    assert (rat.hp, rat.is_defeated, rat.inventory) == (3, False, [])


def test_clone_of_clone_counts_from_the_original_and_respects_the_limit():
    # Act
    context = _run(
        "first = tw.npcs.get('RAT').clone()\n"
        "second = first.clone()\n"
        "for i in range(30):\n"
        "    tw.npcs.clone('RAT')\n",
        {"RAT": _rat_data()},
    )

    # Assert
    clones = context.changeset.cloned_entities
    assert clones[1]["new_id"] == "RAT_2"
    assert len(clones) == 20


def test_clone_of_unknown_npc_returns_none():
    # Act
    context = _run("tw.vars.set('result', tw.npcs.clone('NOBODY'))", {"RAT": _rat_data()})

    # Assert
    assert context.changeset.var_updates["result"] is None
    assert context.changeset.cloned_entities == []


# --- Persistence and a big fight --------------------------------------------------------


async def _seed(db):
    user = User(username="clone_tester", hashed_password="pw", role="user")
    adv = AdventureTemplate(id="adv-clone", title="Pit", owner_id="admin", time_per_turn=5,
                            strict_rules=True, rule_enforcement_mode="rpg")  # fmt: skip
    db.add_all([user, adv])
    await db.flush()
    avatar = Avatar(id="av-clone", template_id=adv.id, user_id=user.id, name="Hero", role="Bard",
                    hp=100, max_hp=100, mana=50, max_mana=50, stamina=100, max_stamina=100,
                    stats={}, inventory=[], equipment={})  # fmt: skip
    state = SessionState(session_id=SESSION_ID, template_id=adv.id, avatar_id=avatar.id,
                         user_id=user.id, current_scene_id="PIT", in_game_time=0,
                         entity_states={"RAT": {"hp": 0, "is_defeated": True}})  # fmt: skip
    rat = WorldEntity(id="RAT", session_id=SESSION_ID, entity_type="NPC", name="Rat",
                      description="A rat.", current_scene_id="PIT", hp=3, max_hp=3,
                      is_hidden=True, is_in_inventory=False,
                      metadata_json={"combat_group": "RAT_PACK"})  # fmt: skip
    db.add_all([avatar, state, rat])
    await db.commit()
    return user


@pytest.mark.asyncio
async def test_cloned_pack_is_stored_fresh_and_fights_together(setup_test_db, monkeypatch):
    monkeypatch.setattr(
        "backend.api.routes.adventures.gameplay_logic.random.randint", lambda *_a, **_k: 20
    )
    monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.random.random", lambda: 1.0)
    monkeypatch.setattr(
        "backend.api.routes.adventures.gameplay_logic.roll_attack", lambda *_a, **_k: dict(MISS)
    )
    async with TestSessionLocal() as db:
        # Arrange: the hidden template rat was beaten earlier; its clones must start fresh.
        user = await _seed(db)
        manager = GameTurnManager(db, SESSION_ID, user)
        await manager.initialize()

        # Act
        await manager._execute_inline_script(
            "for i in range(12):\n    tw.npcs.clone('RAT', hidden=False)", "test", "RAT"
        )
        await db.commit()
        _ = [c async for c in manager.process_turn("/fight RAT_1")]

        # Assert
        rows = (
            (await db.execute(select(WorldEntity).where(WorldEntity.id.like("RAT_%"))))
            .scalars()
            .all()
        )
        assert len(rows) == 12
        assert all(r.hp == 3 and r.is_hidden is False for r in rows)
        assert manager.state.entity_states["RAT_1"].get("is_defeated") is None
        combat = manager._read_combat_state()
        assert len(combat["enemies"]) == 12
        assert all(e["engaged"] for e in combat["enemies"])
        assert len(combat["initiative"]) == 13
