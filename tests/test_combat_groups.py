"""Tests for NPC combat groups: who joins a fight without being attacked."""

import pytest

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.core.world_validator import validate_adventure
from backend.engine.blueprint import analyze_blueprint
from backend.engine.combat.groups import joining_allies, normalize_group, resolve_assist_mode
from backend.engine.manifest_apply.npcs import npc_metadata
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity
from tests.conftest import TestSessionLocal

SESSION_ID = "session-groups"
MISS = {
    "hit_roll": 2, "hit_modifier": 0, "hit_total": 2, "target_ac": 10, "is_hit": False,
    "damage_total": 0, "damage_dice_total": 0, "damage_rolls": [], "damage_bonus": 0,
    "damage_dice_str": "1d6",
}  # fmt: skip


def _fighter(fid, group=None, mode=None, engaged=False):
    return {"id": fid, "name": fid, "combat_group": group,
            "assist_mode": resolve_assist_mode(group, mode), "engaged": engaged}  # fmt: skip


# --- Pure rules ---------------------------------------------------------------------


def test_assist_mode_defaults_to_group_with_a_group_and_never_without():
    # Act / Assert
    assert resolve_assist_mode("BANDITS", None) == "GROUP"
    assert resolve_assist_mode(None, None) == "NEVER"
    assert resolve_assist_mode(None, "anyone") == "ANYONE"
    assert resolve_assist_mode("BANDITS", "bogus") == "GROUP"
    assert normalize_group(" red bandits ") == "RED_BANDITS"
    assert normalize_group("") is None


def test_joining_allies_follows_groups_and_skips_bystanders():
    # Arrange
    leader = _fighter("VAREK", "BANDITS", engaged=True)
    grim = _fighter("GRIM", "BANDITS")
    dog = _fighter("DOG", mode="ANYONE")
    mira = _fighter("MIRA")
    guard = _fighter("GUARD", "GUARDS")

    # Act
    joined = joining_allies([grim, dog, mira, guard], [leader])

    # Assert
    assert [c["id"] for c in joined] == ["GRIM", "DOG"]


def test_joining_allies_chains_through_helpers():
    # Arrange: an ANYONE helper of group WOLVES joins and then pulls its own pack in.
    target = _fighter("MIRA", engaged=True)
    alpha = _fighter("ALPHA", "WOLVES", "ANYONE")
    pup = _fighter("PUP", "WOLVES")

    # Act
    joined = joining_allies([pup, alpha], [target])

    # Assert
    assert {c["id"] for c in joined} == {"ALPHA", "PUP"}


def test_nobody_joins_without_an_engaged_combatant():
    # Act / Assert
    assert joining_allies([_fighter("DOG", mode="ANYONE")], []) == []


# --- Blueprint, manifest and validator ------------------------------------------------


def test_blueprint_group_and_assist_keys_reach_npc_metadata():
    # Arrange
    text = (
        "Bandits ambush the road.\n"
        "[NPC: VAREK] Varek\ngroup: Red Bandits\n"
        "[NPC: GRIM] Grim\ngroup: red bandits\n"
        "[NPC: MIRA] Mira\nassist: bystander\n"
    )

    # Act
    blueprint, _missing = analyze_blueprint(text)
    varek, _grim, mira = blueprint.of_kind("npc")
    meta = npc_metadata({"id": "VAREK", **varek.fixed()})

    # Assert
    assert blueprint.errors == []
    assert varek.fixed()["combat_group"] == "RED_BANDITS"
    assert mira.fixed()["assist_mode"] == "NEVER"
    assert meta["combat_group"] == "RED_BANDITS"


def test_blueprint_rejects_unknown_assist_mode():
    # Act
    blueprint, _missing = analyze_blueprint("[NPC: A] Bob\nassist: sometimes")

    # Assert
    assert any("expected one of GROUP, ANYONE, NEVER" in e.message for e in blueprint.errors)


def test_validator_warns_about_single_member_group():
    # Arrange
    npcs = [
        {"id": "VAREK", "entity_type": "NPC", "metadata_json": {"combat_group": "BANDITS"}},
        {"id": "GRIM", "entity_type": "NPC", "metadata_json": {"combat_group": "BANDITS"}},
        {"id": "SOLO", "entity_type": "NPC", "metadata_json": {"combat_group": "LONERS"}},
    ]
    payload = {"adventure": {"start_scene_id": "S"}, "scenes": [{"id": "S"}], "npcs": npcs,
               "objects": [], "exits": [], "entities_all": npcs}  # fmt: skip

    # Act
    findings = [f for f in validate_adventure(payload) if f.code == "combat_group_single_member"]

    # Assert
    assert [f.context["group"] for f in findings] == ["LONERS"]


# --- Encounters -------------------------------------------------------------------------


def _npc(npc_id, meta=None):
    return WorldEntity(id=npc_id, session_id=SESSION_ID, entity_type="NPC", name=npc_id.title(),
                       description="x", current_scene_id="ROAD", hp=30, max_hp=30,
                       is_hidden=False, is_in_inventory=False, metadata_json=meta or {})  # fmt: skip


async def _seed(db, extra_npcs=()):
    user = User(username="group_tester", hashed_password="pw", role="user")
    adv = AdventureTemplate(id="adv-grp", title="Road", owner_id="admin", time_per_turn=5,
                            strict_rules=True, rule_enforcement_mode="rpg")  # fmt: skip
    db.add_all([user, adv])
    await db.flush()
    avatar = Avatar(id="av-grp", template_id=adv.id, user_id=user.id, name="Hero", role="Bard",
                    hp=100, max_hp=100, mana=50, max_mana=50, stamina=100, max_stamina=100,
                    stats={}, inventory=[], equipment={})  # fmt: skip
    state = SessionState(session_id=SESSION_ID, template_id=adv.id, avatar_id=avatar.id,
                         user_id=user.id, current_scene_id="ROAD", in_game_time=0,
                         entity_states={})  # fmt: skip
    db.add_all([avatar, state,
                _npc("VAREK", {"combat_group": "BANDITS"}),
                _npc("GRIM", {"combat_group": "BANDITS"}),
                _npc("MIRA"),
                *extra_npcs])  # fmt: skip
    await db.commit()
    return user, state


def _patch_dice(monkeypatch):
    monkeypatch.setattr(
        "backend.api.routes.adventures.gameplay_logic.random.randint", lambda *_a, **_k: 20
    )
    monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.random.random", lambda: 1.0)
    monkeypatch.setattr(
        "backend.api.routes.adventures.gameplay_logic.roll_attack", lambda *_a, **_k: dict(MISS)
    )


def _engaged(combat):
    return {e["id"]: e["engaged"] for e in combat["enemies"]}


async def _play(manager, command):
    return [chunk async for chunk in manager.process_turn(command)]


@pytest.mark.asyncio
async def test_attacking_a_group_member_engages_the_group_but_not_bystanders(
    setup_test_db, monkeypatch
):
    async with TestSessionLocal() as db:
        # Arrange
        user, _state = await _seed(db)
        _patch_dice(monkeypatch)
        manager = GameTurnManager(db, SESSION_ID, user)

        # Act
        chunks = await _play(manager, "/fight VAREK")

        # Assert
        combat = manager._read_combat_state()
        assert _engaged(combat) == {"VAREK": True, "GRIM": True, "MIRA": False}
        assert {e["id"] for e in combat["initiative"]} == {"PLAYER", "VAREK", "GRIM"}
        assert any("Grim rushes to help Varek!" in e["text"] for e in combat["log"])
        assert any("1 bystander(s)" in c for c in chunks)


@pytest.mark.asyncio
async def test_attacking_a_bystander_pulls_in_only_that_bystander(setup_test_db, monkeypatch):
    async with TestSessionLocal() as db:
        # Arrange
        user, _state = await _seed(db)
        _patch_dice(monkeypatch)
        manager = GameTurnManager(db, SESSION_ID, user)

        # Act
        await _play(manager, "/fight MIRA")

        # Assert
        combat = manager._read_combat_state()
        assert _engaged(combat) == {"MIRA": True, "VAREK": False, "GRIM": False}


@pytest.mark.asyncio
async def test_attacking_an_idle_group_member_mid_fight_rallies_its_group(
    setup_test_db, monkeypatch
):
    async with TestSessionLocal() as db:
        # Arrange
        user, _state = await _seed(db)
        _patch_dice(monkeypatch)
        manager = GameTurnManager(db, SESSION_ID, user)
        await _play(manager, "/fight MIRA")

        # Act
        await _play(manager, "/attack GRIM")

        # Assert
        assert all(_engaged(manager._read_combat_state()).values())


@pytest.mark.asyncio
async def test_anyone_helper_joins_and_script_can_move_npc_between_groups(
    setup_test_db, monkeypatch
):
    async with TestSessionLocal() as db:
        # Arrange
        dog = _npc("DOG", {"assist_mode": "ANYONE"})
        user, _state = await _seed(db, extra_npcs=[dog])
        _patch_dice(monkeypatch)
        manager = GameTurnManager(db, SESSION_ID, user)
        await manager.initialize()
        await manager._execute_inline_script(
            "tw.npcs.set_combat_group('GRIM', '')\ntw.npcs.set_assist_mode('MIRA', 'group')",
            "test",
            "GRIM",
        )

        # Act
        await _play(manager, "/fight VAREK")

        # Assert
        combat = manager._read_combat_state()
        assert _engaged(combat) == {"VAREK": True, "GRIM": False, "MIRA": False, "DOG": True}
