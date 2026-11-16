"""Respawn instead of game over: settings, revival points, combat knockout, scripting and authoring."""

import pytest

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.api.routes.adventures.respawn_flow import end_or_respawn
from backend.engine.blueprint import analyze_blueprint
from backend.engine.blueprint.merge import apply_blueprint
from backend.engine.rules.respawn import (
    RESPAWN_KEY,
    apply_respawn_point,
    normalize_game_over_rules,
    read_respawn,
    respawn_settings,
    revival_hp,
)
from backend.engine.rules.rule_engine import GameOverError, ProtagonistDownError
from backend.engine.scripting import GameContext
from backend.engine.sessions.scene_entry import enter_scene
from backend.engine.world.scene_fields import scene_content_from_dict
from backend.engine.world.world_schemas import WorldManifesto, WorldSceneSchema
from backend.models.adventure_template import AdventureTemplate
from backend.models.world_entity import WorldScene
from tests.conftest import TestSessionLocal
from tests.test_combat_encounters import SESSION_ID, _patch_dice, _play, _seed

RESPAWN_RULES = {"on_zero_hp": "respawn", "respawn_hp_percent": 25}


# --- settings and record -------------------------------------------------------------------


def test_respawn_settings_default_to_game_over():
    # Arrange / Act / Assert
    assert respawn_settings(None).enabled is False
    assert respawn_settings({"on_zero_hp": "game_over"}).enabled is False
    assert respawn_settings({"on_zero_hp": "respawn"}).hp_percent == 25
    assert respawn_settings({"on_zero_hp": "respawn", "respawn_hp_percent": "40%"}).hp_percent == 40
    assert normalize_game_over_rules({"on_zero_hp": "bogus"})["on_zero_hp"] == "game_over"


def test_revival_hp_is_a_share_of_max_hp_and_at_least_one():
    # Act / Assert
    assert revival_hp(100, 25) == 25
    assert revival_hp(3, 25) == 1


def test_script_respawn_point_is_replayed_into_the_record():
    # Arrange
    states = {RESPAWN_KEY: {"point": "CAMP", "count": 2}}

    # Act
    apply_respawn_point(states, "shrine")
    moved = read_respawn(states)
    apply_respawn_point(states, "")

    # Assert
    assert moved == {"point": "SHRINE", "count": 2}
    assert read_respawn(states) == {"point": None, "count": 2}


def test_tw_game_exposes_and_sets_the_respawn_point():
    # Arrange
    ctx = GameContext(respawn={"point": "CAMP", "count": 1})

    # Act
    before = (ctx.game.respawn_point, ctx.game.respawns)
    ctx.game.set_respawn_point("shrine")

    # Assert
    assert before == ("CAMP", 1)
    assert ctx.game.respawn_point == "SHRINE"
    assert ctx.changeset.respawn_point == "SHRINE" and ctx.changeset.has_changes


# --- authoring -------------------------------------------------------------------------------


def test_blueprint_keys_reach_the_manifest():
    # Arrange
    text = (
        "[World]\nat_zero_hp: respawn\nrespawn_hp: 30%\n"
        "[Scene: CAMP] Camp\nrespawn: yes\n"
        "[Sequence: FINALE] Finale\nrespawn: no\n"
    )
    manifest = {"scenes": [], "sequences": []}

    # Act
    blueprint, _ = analyze_blueprint(text)
    apply_blueprint(manifest, blueprint)

    # Assert
    assert blueprint.issues == []
    assert manifest["game_over_rules"] == {"on_zero_hp": "respawn", "respawn_hp_percent": 30}
    scene = next(b for b in blueprint.blocks if b.kind == "scene")
    sequence = next(b for b in blueprint.blocks if b.kind == "sequence")
    assert scene.fields["is_respawn_point"].value is True
    assert sequence.fields["respawn_allowed"].value is False


def test_generation_schema_and_scene_copy_keep_the_fields():
    # Arrange
    scene = WorldSceneSchema(id="CAMP", name="Camp", description="A fire.", is_respawn_point=True)

    # Act
    dumped = scene.model_dump()
    rules_field = WorldManifesto.model_fields["game_over_rules"]

    # Assert
    assert scene_content_from_dict(dumped)["is_respawn_point"] is True
    assert scene_content_from_dict({"id": "X"})["is_respawn_point"] is False
    assert rules_field.default is None


# --- runtime -----------------------------------------------------------------------------------


async def _seed_world(db, rules=RESPAWN_RULES, sequences=None):
    user, avatar, state = await _seed(db)
    adv = await db.get(AdventureTemplate, "adv-enc")
    adv.game_over_rules = rules
    adv.sequences = sequences
    adv.original_manifest = {"start_scene_id": "START"}
    for scene_id, revival in (("START", False), ("CAMP", True), ("ARENA", False)):
        db.add(
            WorldScene(
                id=scene_id,
                template_id="adv-enc",
                label=scene_id.title(),
                description=f"The {scene_id.lower()}.",
                is_respawn_point=revival,
            )
        )
    await db.commit()
    return user, avatar, state


@pytest.mark.asyncio
async def test_hp_zero_respawns_at_the_start_scene(setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange
        user, _avatar, _state = await _seed_world(db)
        manager = GameTurnManager(db, SESSION_ID, user)
        await manager.initialize()
        manager.avatar.hp = 0
        manager.avatar.status_effects = ["Poisoned"]

        # Act
        ended = await end_or_respawn(manager, ProtagonistDownError("Hero has fallen!"))

        # Assert
        assert ended is False
        assert manager.avatar.hp == 25 and manager.avatar.status_effects == []
        assert manager.state.current_scene_id == "START"
        assert read_respawn(manager.state.entity_states)["count"] == 1


@pytest.mark.asyncio
async def test_deliberate_defeat_and_default_mode_stay_final(setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange
        user, _avatar, _state = await _seed_world(db)
        manager = GameTurnManager(db, SESSION_ID, user)
        await manager.initialize()

        # Act
        scripted = await end_or_respawn(manager, GameOverError("The bomb exploded."))

        # Assert
        assert scripted is True
        assert manager.state.current_scene_id == "ARENA"


@pytest.mark.asyncio
async def test_deadly_sequence_forbids_respawn(setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange
        sequences = [{"id": "FINALE", "name": "Finale", "respawn_allowed": False}]
        user, _avatar, state = await _seed_world(db, sequences=sequences)
        state.active_sequence_id = "FINALE"
        await db.commit()
        manager = GameTurnManager(db, SESSION_ID, user)
        await manager.initialize()

        # Act
        ended = await end_or_respawn(manager, ProtagonistDownError("Hero has fallen!"))

        # Assert
        assert ended is True


@pytest.mark.asyncio
async def test_entering_a_revival_point_records_it_and_respawn_uses_it(setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange
        user, _avatar, _state = await _seed_world(db)
        manager = GameTurnManager(db, SESSION_ID, user)
        await manager.initialize()
        manager.state.current_scene_id = "CAMP"

        # Act
        notices = await enter_scene(db, manager.state, "ARENA", adventure=manager.adventure)
        manager.state.current_scene_id = "ARENA"
        await end_or_respawn(manager, ProtagonistDownError("Hero has fallen!"))

        # Assert
        assert notices == ["Revival point reached: Camp."]
        assert manager.state.current_scene_id == "CAMP"


@pytest.mark.asyncio
async def test_on_respawn_script_runs_after_the_revival(setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange
        user, _avatar, _state = await _seed_world(db)
        adv = await db.get(AdventureTemplate, "adv-enc")
        adv.scripts = [
            {
                "id": "PENALTY",
                "trigger": "on_respawn",
                "code": "tw.vars.set('woke_up', tw.game.respawns)",
            }
        ]
        await db.commit()
        manager = GameTurnManager(db, SESSION_ID, user)
        await manager.initialize()

        # Act
        await end_or_respawn(manager, ProtagonistDownError("Hero has fallen!"))

        # Assert
        script_vars = (manager.state.entity_states or {}).get("__script_vars__", {})
        assert script_vars.get("woke_up") == 1


@pytest.mark.asyncio
async def test_combat_defeat_knocks_the_protagonist_out(setup_test_db, monkeypatch):
    async with TestSessionLocal() as db:
        # Arrange
        user, _avatar, _state = await _seed_world(db)
        _patch_dice(monkeypatch)
        manager = GameTurnManager(db, SESSION_ID, user)
        await _play(manager, "/fight GOBLIN")
        combat = manager._read_combat_state()
        manager.avatar.hp = 0

        # Act
        await manager.combat._handle_player_defeat(combat, "The protagonist falls.")

        # Assert
        assert combat["outcome"] == "knocked_out" and combat["active"] is False
        assert manager.avatar.hp == 25
        assert manager.state.current_scene_id == "START"
        status = manager.state.session.status if manager.state.session else None
        assert status != "game_over"
