"""Tests for procedural Dynamic Scenes schemas, validation, materialization, checkpoints, and export."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from backend.api.routes.adventures import dynamic_scene_flow
from backend.api.routes.adventures.dynamic_scene_flow import (
    materialize_dynamic_scene_for_exit,
    sync_dynamic_scene_audio,
)
from backend.core.world_validation.context import ValidationContext
from backend.core.world_validation.topology import check_exit_targets_exist
from backend.engine.adventures.adventure_exporter import AdventureExporter
from backend.engine.audio.audio_state import read_audio_state
from backend.engine.blueprint import analyze_blueprint, apply_blueprint
from backend.engine.interaction.map_engine import MapEngine
from backend.engine.sessions.session_snapshot import dump_world, restore_world
from backend.engine.world.dynamic_scene_schemas import (
    DynamicGeneratedChildExit,
    DynamicGeneratedNpc,
    DynamicGeneratedObject,
    DynamicGeneratedScenePayload,
    build_dynamic_placeholder_scene_id,
    normalize_dynamic_generation,
    normalize_dynamic_zone,
)
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene


def test_normalization_helpers_and_placeholder_id() -> None:
    """Verify dynamic zone/generation normalization and deterministic scene IDs."""
    # Arrange & Act
    disabled = normalize_dynamic_zone({"enabled": False, "theme": "Mines"})
    missing_theme = normalize_dynamic_zone({"enabled": True, "zone_id": "mines", "theme": "   "})
    normalized = normalize_dynamic_zone(
        {
            "zone_id": "Iron Mines!",
            "theme": "Abandoned dwarven mine",
            "depth": 9,
            "max_depth": 4,
            "danger_level": "HIGH",
        }
    )
    gen_cfg = normalize_dynamic_generation({"scene_image_mode": "hq", "audio_mode": "generate"})
    placeholder = build_dynamic_placeholder_scene_id("Iron Mines!", depth=2, index=1, suffix="a1b2")

    # Assert
    assert disabled is None
    assert missing_theme is None
    assert normalized is not None
    assert normalized["zone_id"] == "iron_mines"
    assert normalized["max_depth"] == 4
    assert normalized["depth"] == 4
    assert normalized["danger_level"] == "high"
    assert gen_cfg == {
        "scene_image_mode": "hq",
        "npc_image_mode": "simple",
        "audio_mode": "generate",
        "interlude_quote_enabled": True,
    }
    assert placeholder == "DYN_IRON_MINES_D2_1_A1B2"


def test_validator_skips_dynamic_exit_targets() -> None:
    """Topology validator skips missing scene errors only for enabled dynamic exits."""
    # Arrange
    exits = [
        {
            "id": "E_DYN",
            "from_scene_id": "HUB",
            "to_scene_id": "DYN_MINES_D1_1",
            "dynamic_zone": {"enabled": True, "zone_id": "mines", "theme": "Deep shaft"},
        },
        {
            "id": "E_BROKEN",
            "from_scene_id": "HUB",
            "to_scene_id": "MISSING_SCENE",
        },
    ]
    ctx = ValidationContext.from_payload(
        {
            "adventure": {"start_scene_id": "HUB"},
            "scenes": [{"id": "HUB", "label": "Hub"}],
            "exits": exits,
        }
    )

    # Act
    findings = check_exit_targets_exist(ctx)

    # Assert
    assert len(findings) == 1
    assert findings[0].code == "exit_to_missing_scene"
    assert findings[0].context is not None
    assert findings[0].context.get("exit_id") == "E_BROKEN"


async def _seed_dynamic_session(db_session, audio_mode: str = "inherit"):
    user = User(
        id=str(uuid.uuid4()),
        username=f"tester_{uuid.uuid4().hex[:8]}",
        hashed_password="x",
    )
    adv_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    adv = AdventureTemplate(
        id=adv_id,
        owner_id=user.id,
        title="Dwarven Frontier",
        teaser="Into the earth",
        plot="Explore the old mine",
        is_ready=True,
        dynamic_generation={
            "scene_image_mode": "off",
            "npc_image_mode": "off",
            "audio_mode": audio_mode,
            "interlude_quote_enabled": True,
        },
    )
    avatar = Avatar(id=str(uuid.uuid4()), user_id=user.id, template_id=adv_id, name="Hero")
    game = GameSession(id=session_id, template_id=adv_id, user_id=user.id, avatar_id=avatar.id)
    state = SessionState(
        session_id=session_id,
        template_id=adv_id,
        user_id=user.id,
        avatar_id=avatar.id,
        current_scene_id="TOWN_GATE",
    )
    origin_scene = WorldScene(
        id="TOWN_GATE",
        template_id=None,
        session_id=session_id,
        label="Town Gate",
        description="A misty stone archway.",
        audio_track_id="GATE_THEME",
    )
    dyn_exit = WorldExit(
        id="EXIT_MINE",
        template_id=None,
        session_id=session_id,
        from_scene_id="TOWN_GATE",
        to_scene_id="DYN_IRON_MINES_D1_1",
        label="Collapsed Mine Shaft",
        exit_type="one_way",
        dynamic_zone={
            "enabled": True,
            "zone_id": "iron_mines",
            "theme": "Flooded dwarven mine shaft",
            "depth": 1,
            "max_depth": 2,
            "danger_level": "medium",
            "cul_de_sac_on_max_depth": True,
        },
    )
    existing_npc = WorldEntity(
        id="NPC_MINER",
        template_id=None,
        session_id=session_id,
        entity_type="NPC",
        name="Old Borin",
        description="A grizzled veteran prospector.",
        current_scene_id="TOWN_GATE",
    )
    db_session.add_all([user, adv, game, avatar, state, origin_scene, dyn_exit, existing_npc])
    await db_session.commit()
    return user, adv, state, origin_scene, dyn_exit


@pytest.mark.asyncio
async def test_materialize_dynamic_scene_depth_idempotency_and_interlude(
    db_session, monkeypatch
) -> None:
    """Materialization creates session rows, forward child exits, interlude SSE, and cul-de-sac stop."""
    # Arrange
    user, adv, state, origin_scene, dyn_exit = await _seed_dynamic_session(
        db_session, audio_mode="generate"
    )
    sse_events: list[tuple[str, dict]] = []

    async def _fake_emit(event_name: str, data: dict) -> None:
        sse_events.append((event_name, data))

    async def _fake_interlude(**kwargs):
        return {
            "quote": "Keep your lantern close down there.",
            "speaker_name": "Old Borin",
            "speaker_role": "Prospector",
            "npc_id": "NPC_MINER",
        }

    async def _fake_scene_payload(**kwargs):
        zone = kwargs["dynamic_zone"]
        return DynamicGeneratedScenePayload(
            name=f"Level {zone['depth']} Gallery",
            description="Damp timber and glinting veins of ore.",
            visual_description="Abandoned stone tunnel",
            music_prompt="Echoing subterranean cavern ambience",
            npcs=[
                DynamicGeneratedNpc(
                    id="GOBLIN_SCOUT",
                    name="Tunnel Goblin",
                    role="Scavenger",
                    description="Hunches behind an overturned cart.",
                    attitude="hostile",
                    combat_role="minion",
                )
            ],
            objects=[
                DynamicGeneratedObject(
                    id="IRON_TONIC",
                    name="Stale Rations",
                    item_type="CONSUMABLE",
                    description="Preserved dwarf hardtack.",
                    effect_type="heal",
                    effect_value=15,
                )
            ],
            forward_exits=[
                DynamicGeneratedChildExit(
                    label="Steeper Ore Chute",
                    theme_hint="Deep flooded crystal vein",
                )
            ],
        )

    monkeypatch.setattr(dynamic_scene_flow, "generate_dynamic_interlude_quote", _fake_interlude)
    monkeypatch.setattr(dynamic_scene_flow, "generate_dynamic_scene_payload", _fake_scene_payload)

    # Act: First entry at depth 1 (< max_depth 2)
    scene_d1 = await materialize_dynamic_scene_for_exit(
        db=db_session,
        state=state,
        adventure=adv,
        user=user,
        world_exit=dyn_exit,
        origin_scene=origin_scene,
        emit_sse=_fake_emit,
    )
    await db_session.commit()

    # Second entry into already materialized scene must be idempotent
    sse_count_before = len(sse_events)
    scene_d1_again = await materialize_dynamic_scene_for_exit(
        db=db_session,
        state=state,
        adventure=adv,
        user=user,
        world_exit=dyn_exit,
        origin_scene=origin_scene,
        emit_sse=_fake_emit,
    )

    # Find child dynamic exit from D1 -> enter D2 (max_depth == 2 -> cul-de-sac)
    child_exits = (
        (
            await db_session.execute(
                select(WorldExit).where(
                    WorldExit.session_id == state.session_id,
                    WorldExit.from_scene_id == scene_d1.id,
                    WorldExit.dynamic_zone.is_not(None),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(child_exits) == 1
    scene_d2 = await materialize_dynamic_scene_for_exit(
        db=db_session,
        state=state,
        adventure=adv,
        user=user,
        world_exit=child_exits[0],
        origin_scene=scene_d1,
    )
    await db_session.commit()

    d2_child_dyn_exits = (
        (
            await db_session.execute(
                select(WorldExit).where(
                    WorldExit.session_id == state.session_id,
                    WorldExit.from_scene_id == scene_d2.id,
                    WorldExit.dynamic_zone.is_not(None),
                )
            )
        )
        .scalars()
        .all()
    )

    # Assert
    assert scene_d1_again.id == scene_d1.id
    assert len(sse_events) == sse_count_before
    assert any(
        ev == "dynamic_interlude" and "Keep your lantern" in data["quote"]
        for ev, data in sse_events
    )
    assert scene_d1.label == "Level 1 Gallery"
    assert scene_d2.label == "Level 2 Gallery"
    assert d2_child_dyn_exits == []

    # Verify generated audio is scoped and releases when leaving back to authored scene
    audio_in_mine = read_audio_state(state.entity_states)
    assert audio_in_mine["now"] is not None
    sync_dynamic_scene_audio(state, "TOWN_GATE")
    audio_at_gate = read_audio_state(state.entity_states)
    assert audio_at_gate["now"] is None

    # Verify checkpoint dump/restore preserves dynamic WorldScene rows and exit dynamic_zone
    world_dump = await dump_world(db_session, state.session_id)
    assert any(s["id"] == scene_d1.id for s in world_dump["scenes"])
    await db_session.delete(scene_d2)
    await db_session.commit()
    await restore_world(db_session, state, world_dump)
    await db_session.commit()
    restored_d2 = (
        (
            await db_session.execute(
                select(WorldScene).where(
                    WorldScene.session_id == state.session_id,
                    WorldScene.id == scene_d2.id,
                )
            )
        )
        .scalars()
        .first()
    )
    assert restored_d2 is not None


@pytest.mark.asyncio
async def test_adventure_exporter_includes_dynamic_settings_and_exits(db_session) -> None:
    """AdventureExporter includes adventure.dynamic_generation and exit.dynamic_zone."""
    # Arrange
    user = User(
        id=str(uuid.uuid4()),
        username=f"exporter_{uuid.uuid4().hex[:8]}",
        hashed_password="x",
    )
    adv_id = str(uuid.uuid4())
    adv = AdventureTemplate(
        id=adv_id,
        owner_id=user.id,
        title="Export Test",
        is_ready=True,
        dynamic_generation={
            "scene_image_mode": "hq",
            "npc_image_mode": "off",
            "audio_mode": "empty",
            "interlude_quote_enabled": False,
        },
    )
    scene = WorldScene(
        id="START",
        template_id=adv_id,
        label="Start",
        description="Origin",
    )
    dyn_exit = WorldExit(
        id="EXIT_1",
        template_id=adv_id,
        from_scene_id="START",
        to_scene_id="DYN_CATACOMBS_D1_1",
        label="Catacomb Stairs",
        exit_type="one_way",
        dynamic_zone={
            "enabled": True,
            "zone_id": "catacombs",
            "theme": "Ancient bone catacombs",
            "depth": 1,
            "max_depth": 3,
            "danger_level": "medium",
            "cul_de_sac_on_max_depth": True,
        },
    )
    db_session.add_all([user, adv, scene, dyn_exit])
    await db_session.commit()

    # Act
    manifest = await AdventureExporter.build_full_manifest(db_session, adv_id)

    # Assert
    assert manifest["adventure"]["dynamic_generation"]["scene_image_mode"] == "hq"
    assert manifest["adventure"]["dynamic_generation"]["audio_mode"] == "empty"
    assert len(manifest["exits"]) == 1
    assert manifest["exits"][0]["dynamic_zone"]["zone_id"] == "catacombs"


def test_blueprint_dynamic_world_and_exit_roundtrip() -> None:
    """Blueprints can configure world.dynamic_generation and dynamic exits cleanly."""
    # Arrange
    source = """
    [World]
    dynamic_scene_images: simple
    dynamic_npc_images: hq
    dynamic_audio: inherit
    dynamic_quotes: yes

    [Scene: HALL] Mine Entrance
    Timbered archway leading underground.

    [Exit: HALL -> IRON_MINES] Collapsed Mine Shaft
    theme: Abandoned dwarven iron mine, flooded ore tracks
    max_depth: 3
    danger: high
    cul_de_sac: yes
    allowed_entities: hostile_npc, container
    """

    # Act
    blueprint, missing_ids = analyze_blueprint(source)
    manifest: dict = {"scenes": [{"id": "HALL", "label": "Mine Entrance"}], "exits": []}
    violations = apply_blueprint(manifest, blueprint)

    # Assert
    assert blueprint.errors == []
    assert "IRON_MINES" not in missing_ids
    assert not any(mid.startswith("DYN_") for mid in missing_ids)
    assert violations == []
    assert manifest["dynamic_generation"] == {
        "scene_image_mode": "simple",
        "npc_image_mode": "hq",
        "audio_mode": "inherit",
        "interlude_quote_enabled": True,
    }
    assert len(manifest["exits"]) == 1
    dyn_exit = manifest["exits"][0]
    assert dyn_exit["from_scene_id"] == "HALL"
    assert dyn_exit["to_scene_id"].startswith("DYN_IRON_MINES_D1_")
    assert dyn_exit["dynamic_zone"]["zone_id"] == "iron_mines"
    assert dyn_exit["dynamic_zone"]["max_depth"] == 3
    assert dyn_exit["dynamic_zone"]["danger_level"] == "high"
    assert dyn_exit["dynamic_zone"]["allowed_entity_types"] == ["hostile_npc", "container"]


def test_map_engine_marks_dynamic_target_nodes_and_edges() -> None:
    """MapEngine.augment_map_data sets is_dynamic and dynamic_zone on targets and edges."""
    # Arrange
    map_dict = {
        "nodes": {"HALL": {"id": "HALL", "label": "Hall", "description": "", "image_url": None}},
        "edges": [],
        "current_scene_id": "HALL",
    }
    dyn_exit = WorldExit(
        id="EXIT_DYN",
        template_id="tpl",
        from_scene_id="HALL",
        to_scene_id="DYN_IRON_MINES_D1_ABC123",
        label="Collapsed Mine Shaft",
        exit_type="one_way",
        dynamic_zone={
            "enabled": True,
            "zone_id": "iron_mines",
            "theme": "Flooded mine",
            "depth": 1,
            "max_depth": 3,
            "danger_level": "medium",
            "cul_de_sac_on_max_depth": True,
        },
    )

    # Act
    augmented = MapEngine.augment_map_data(map_dict, [dyn_exit], "HALL")
    target_key = MapEngine._safe_id(dyn_exit.to_scene_id)

    # Assert
    target_node = augmented["nodes"][target_key]
    assert target_node["is_unknown"] is True
    assert target_node["is_dynamic"] is True
    assert target_node["dynamic_zone"]["zone_id"] == "iron_mines"
    assert len(augmented["edges"]) == 1
    assert augmented["edges"][0]["dynamic_zone"]["zone_id"] == "iron_mines"
