"""Tests for special attack unlocks, NPC attack triggers and special attack scripts."""

import json

import pytest
from sqlalchemy import select

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.api.routes.adventures.post_turn_hooks import PostTurnHooks
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.chat import ChatMessage
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio

SESSION_ID = "session-triggers"
FINAL = 'event: final\ndata: {"status": "success"}\n\n'


async def _seed(db, npc_meta=None, specials=None, unlocked=None):
    user = User(username="trigger_tester", hashed_password="pw", role="user")
    adv = AdventureTemplate(
        id="adv-trig",
        title="Triggers",
        owner_id="admin",
        time_per_turn=5,
        strict_rules=True,
        rule_enforcement_mode="rpg",
    )
    db.add_all([user, adv])
    await db.flush()
    avatar = Avatar(id="av-trig", template_id=adv.id, user_id=user.id, name="Hero", role="Bard",
                    hp=100, max_hp=100, mana=50, max_mana=50, stamina=100, max_stamina=100,
                    stats={"special_actions": specials or [], "unlocked_actions": unlocked or []},
                    inventory=[], equipment={})  # fmt: skip
    state = SessionState(session_id=SESSION_ID, template_id=adv.id, avatar_id=avatar.id,
                         user_id=user.id, current_scene_id="VAULT", in_game_time=0, entity_states={})  # fmt: skip
    guard = WorldEntity(id="GUARD", session_id=SESSION_ID, entity_type="NPC", name="Vault Guard",
                        description="Stern.", current_scene_id="VAULT", hp=30, max_hp=30,
                        is_hidden=False, is_in_inventory=False, metadata_json=npc_meta or {})  # fmt: skip
    db.add_all([avatar, state, guard])
    await db.commit()
    return user, avatar, state


async def _run_hooks(user, db):
    manager = GameTurnManager(db, SESSION_ID, user)
    await manager.initialize()
    chunks = [c async for c in PostTurnHooks(manager).process_final(FINAL)]
    return manager, chunks


async def test_attack_on_sight_starts_fight_on_scene_entry(setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange
        user, _avatar, _state = await _seed(db, npc_meta={"attack_mode": "ATTACK_ON_SIGHT"})

        # Act
        manager, chunks = await _run_hooks(user, db)
        _manager2, chunks_again = await _run_hooks(user, db)

        # Assert
        combat = manager._read_combat_state()
        assert combat.get("active") is True
        assert combat["enemies"][0]["id"] == "GUARD"
        final = json.loads(chunks[-1].split("data: ", 1)[1])
        assert final["combat"]["active"] is True
        assert any("attacks on sight" in c for c in chunks)
        assert len(chunks_again) == 1  # combat already running, nothing new


async def test_item_trigger_fires_once_when_item_is_taken(setup_test_db):
    trigger = {"attack_trigger": {"required_item_id": "IDOL"}}
    async with TestSessionLocal() as db:
        # Arrange
        user, avatar, state = await _seed(db, npc_meta=trigger)
        state.entity_states = {"__last_scene_id__": "VAULT"}
        await db.commit()
        _m, before = await _run_hooks(user, db)
        avatar.inventory = [{"id": "IDOL", "name": "Golden Idol"}]
        await db.commit()

        # Act
        manager, chunks = await _run_hooks(user, db)

        # Assert
        assert before == [FINAL]
        assert manager._read_combat_state().get("active") is True
        assert (manager.state.entity_states["GUARD"] or {}).get("attack_trigger_fired") is True
        assert any("turns hostile" in c for c in chunks)


async def test_script_attack_request_starts_fight(setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange
        user, _avatar, state = await _seed(db)
        state.entity_states = {"__last_scene_id__": "VAULT"}
        await db.commit()
        manager = GameTurnManager(db, SESSION_ID, user)
        await manager.initialize()

        # Act
        await manager._execute_inline_script("tw.npcs.get('GUARD').attack()", "test", "GUARD")
        _ = [c async for c in PostTurnHooks(manager).process_final(FINAL)]

        # Assert
        assert manager._read_combat_state().get("active") is True


async def test_special_unlocks_by_item_rule_with_system_message(setup_test_db):
    special = {"id": "SMITE", "name": "Holy Smite", "action_type": "ATTACK", "is_locked": True,
               "unlock_required_item_id": "RELIC", "unlock_text": "The relic hums."}  # fmt: skip
    async with TestSessionLocal() as db:
        # Arrange
        user, avatar, state = await _seed(db, specials=[special])
        state.entity_states = {"__last_scene_id__": "VAULT"}
        avatar.inventory = [{"id": "RELIC", "name": "Relic"}]
        await db.commit()

        # Act
        manager, chunks = await _run_hooks(user, db)

        # Assert
        assert "SMITE" in manager.avatar.stats["unlocked_actions"]
        assert any("Special attack unlocked: Holy Smite! The relic hums." in c for c in chunks)
        msgs = (
            (await db.execute(select(ChatMessage).where(ChatMessage.session_id == SESSION_ID)))
            .scalars()
            .all()
        )
        assert any("Holy Smite" in m.content for m in msgs)


async def test_special_success_script_runs_with_special_scope(setup_test_db, monkeypatch):
    special = {"id": "CHEER", "name": "Cheer", "action_type": "UTILITY", "cost": 0,
               "effects": [{"target": "self", "stat": "stamina", "amount": "+1"}],
               "on_success_script": "tw.vars.set('cheered_by', special['caster'])",
               "on_success_text": "The crowd roars!"}  # fmt: skip
    async with TestSessionLocal() as db:
        # Arrange
        user, _avatar, state = await _seed(db, specials=[special], unlocked=["CHEER"])
        state.entity_states = {"__last_scene_id__": "VAULT"}
        await db.commit()
        monkeypatch.setattr(
            "backend.api.routes.adventures.gameplay_logic.random.randint", lambda *_a, **_k: 20
        )
        monkeypatch.setattr(
            "backend.api.routes.adventures.gameplay_logic.random.random", lambda: 1.0
        )
        manager = GameTurnManager(db, SESSION_ID, user)
        _ = [c async for c in manager.process_turn("/fight GUARD")]

        # Act
        chunks = [c async for c in manager.process_turn("/special CHEER")]

        # Assert
        assert any("The crowd roars!" in c for c in chunks)
        script_vars = (manager.state.entity_states or {}).get("__script_vars__") or {}
        assert (
            script_vars.get("cheered_by") == "PLAYER"
            or manager.state.custom_variables.get("cheered_by") == "PLAYER"
        )


async def test_npc_combat_endpoint_validates_guard(auth_client, setup_test_db):
    async with TestSessionLocal() as db:
        user = (
            (await db.execute(select(User).where(User.username == "test_user"))).scalars().first()
        )
        adv = AdventureTemplate(
            title="NPC combat", owner_id=user.id, original_manifest={"npcs": [{"id": "OGRE"}]}
        )
        db.add(adv)
        await db.flush()
        db.add(WorldEntity(id="OGRE", template_id=adv.id, entity_type="NPC", name="Ogre",
                           description="Big.", current_scene_id="CAVE", metadata_json={}))  # fmt: skip
        await db.commit()
        template_id = adv.id

    # Act
    bad = await auth_client.put(f"/api/adventures/{template_id}/editor/npc-combat",
                                json={"npc_id": "OGRE", "attack_trigger": {"guard_expression": "import os"}})  # fmt: skip
    good = await auth_client.put(
        f"/api/adventures/{template_id}/editor/npc-combat",
        json={"npc_id": "OGRE", "attack_mode": "ATTACK_ON_SIGHT", "special_chance": 70,
              "attack_trigger": {"required_item_id": "IDOL", "guard_expression": "tw.player.hp > 0"}},
    )  # fmt: skip

    # Assert
    assert bad.status_code == 400
    assert good.status_code == 200
    async with TestSessionLocal() as db:
        npc = (
            (await db.execute(select(WorldEntity).where(WorldEntity.id == "OGRE")))
            .scalars()
            .first()
        )
        assert npc.metadata_json["attack_mode"] == "ATTACK_ON_SIGHT"
        assert npc.metadata_json["attack_trigger"]["required_item_id"] == "IDOL"
        assert npc.metadata_json["special_chance"] == 70
