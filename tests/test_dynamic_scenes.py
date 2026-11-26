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
from backend.engine.world import dynamic_scene_generator
from backend.engine.world.dynamic_scene_schemas import (
    DynamicGeneratedChildExit,
    DynamicGeneratedNpc,
    DynamicGeneratedObject,
    DynamicGeneratedScenePayload,
    DynamicInterludeQuotePayload,
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
        "item_image_mode": "simple",
        "audio_mode": "generate",
        "generation_model": "mechanics",
        "max_npcs": 2,
        "npc_type_caps": {"humanoid": 2, "being": 2, "animal": 2, "monster": 2},
        "spawn_chances": {
            "npc": 55,
            "enemy": 35,
            "humanoid": 50,
            "being": 20,
            "animal": 30,
            "monster": 25,
            "item": 75,
            "container": 30,
            "switch": 20,
        },
        "interlude_quote_enabled": True,
    }
    expected_placeholder = build_dynamic_placeholder_scene_id(
        "iron_mines",
        depth=2,
        index=1,
        suffix="A1B2",
    )
    assert placeholder == expected_placeholder
    assert placeholder.startswith("DYN_")
    assert len(placeholder) <= 20
    assert all(ch.isupper() or ch.isdigit() or ch == "_" for ch in placeholder)


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
    dynamic_item_images: off
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
        "item_image_mode": "off",
        "audio_mode": "inherit",
        "generation_model": "mechanics",
        "max_npcs": 2,
        "npc_type_caps": {"humanoid": 2, "being": 2, "animal": 2, "monster": 2},
        "spawn_chances": {
            "npc": 55,
            "enemy": 35,
            "humanoid": 50,
            "being": 20,
            "animal": 30,
            "monster": 25,
            "item": 75,
            "container": 30,
            "switch": 20,
        },
        "interlude_quote_enabled": True,
    }
    assert len(manifest["exits"]) == 1
    dyn_exit = manifest["exits"][0]
    assert dyn_exit["from_scene_id"] == "HALL"
    assert dyn_exit["to_scene_id"] == build_dynamic_placeholder_scene_id(
        "iron_mines",
        depth=1,
        index=1,
        suffix="HALLCollapsed Mine Shaft",
    )
    assert dyn_exit["to_scene_id"].startswith("DYN_")
    assert len(dyn_exit["to_scene_id"]) <= 20
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


@pytest.mark.asyncio
async def test_generate_dynamic_interlude_quote_returns_frontend_fields(
    db_session, monkeypatch
) -> None:
    """Interlude generator emits speaker_name, speaker_role, npc_id, voice, image_url, and quote."""

    # Arrange
    class _FakeLLM:
        def __init__(self, user, provider=None, model_category=None):
            del user, provider, model_category

        async def aexecute_complex_task(self, *args, **kwargs):
            del args, kwargs
            return DynamicInterludeQuotePayload(
                speaker="Ignored Fallback",
                role="Scout",
                quote='"Keep your blade dry in the dark."',
            )

    monkeypatch.setattr(dynamic_scene_generator, "GameMasterLLM", _FakeLLM)
    monkeypatch.setattr(dynamic_scene_generator, "_has_provider_credentials", lambda *_: True)

    user = User(
        id=str(uuid.uuid4()),
        username=f"quote_tester_{uuid.uuid4().hex[:8]}",
        hashed_password="x",
    )

    # Act
    result = await dynamic_scene_generator.generate_dynamic_interlude_quote(
        adventure_title="Dwarven Frontier",
        adventure_setting="Beneath the iron peaks",
        adventure_tone="Grim",
        origin_scene_name="Town Gate",
        exit_label="Mine Shaft",
        zone_theme="Flooded mine",
        candidate_npcs=[
            {
                "id": "NPC_MINER",
                "name": "Old Borin",
                "role": "Prospector",
                "character": "Cautious",
                "description": "Grizzled miner",
                "image_url": "/images/borin.png",
                "voice": "en-US-Standard-B",
                "is_defeated": False,
            }
        ],
        user=user,
        db=db_session,
        language="English",
    )

    # Assert
    assert result is not None
    assert result["quote"] == "Keep your blade dry in the dark."
    assert result["speaker_name"] == "Old Borin"
    assert result["speaker_role"] == "Prospector"
    assert result["npc_id"] == "NPC_MINER"
    assert result["voice"] == "en-US-Standard-B"
    assert result["image_url"] == "/images/borin.png"
    assert result["speaker"] == "Old Borin"
    assert result["role"] == "Prospector"
    assert result["avatar_url"] == "/images/borin.png"


@pytest.mark.asyncio
async def test_generate_dynamic_visuals_includes_item_images(monkeypatch) -> None:
    """generate_dynamic_visuals generates item artwork when item_image_mode is simple or hq."""
    # Arrange
    from backend.api.routes.adventures import dynamic_scene_media

    calls: list[tuple[str, str]] = []

    async def _fake_generate_tier_image(**kwargs):
        calls.append((kwargs["prefix"], kwargs["tier"]))
        return f"/data/adventures/sessions/s1/dynamic_assets/{kwargs['prefix']}.webp"

    monkeypatch.setattr(dynamic_scene_media, "_generate_tier_image", _fake_generate_tier_image)

    payload = DynamicGeneratedScenePayload(
        name="Forgotten Vault",
        description="A dusty subterranean chamber.",
        npcs=[
            DynamicGeneratedNpc(
                id="WARDEN",
                name="Clockwork Warden",
                description="Brass sentinel.",
            )
        ],
        objects=[
            DynamicGeneratedObject(
                id="LANTERN",
                name="Brass Lantern",
                description="Burns with a pale blue flame.",
                visual_description="ornate brass lantern, blue flame",
            )
        ],
    )

    # Act
    scene_img, npc_imgs, obj_imgs = await dynamic_scene_media.generate_dynamic_visuals(
        payload=payload,
        dyn_cfg={"scene_image_mode": "off", "npc_image_mode": "off", "item_image_mode": "hq"},
        origin_scene=None,
        user=object(),
        adventure=AdventureTemplate(id="adv1", owner_id="u1", title="Vault"),
        session_id="s1",
        target_id="DYN_VAULT_D1_1",
    )

    # Assert
    assert scene_img is None
    assert npc_imgs == {}
    assert obj_imgs == {
        0: "/data/adventures/sessions/s1/dynamic_assets/dyn_obj_dyn_vault_d1_1_0.webp"
    }
    assert calls == [("dyn_obj_dyn_vault_d1_1_0", "hq")]


def test_dynamic_zone_new_options_and_id_cap() -> None:
    """Zone normalization handles peaceful/random danger, max_npcs, audio_mode aliases, and ID length."""
    # Arrange & Act
    peaceful_zone = normalize_dynamic_zone(
        {
            "zone_id": "quiet_meadow_sanctuary_with_very_long_name",
            "theme": "Sunlit alpine meadow with wildflowers",
            "danger_level": "peaceful",
            "max_npcs": 9,
            "audio_mode": "off",
        }
    )
    random_zone = normalize_dynamic_zone(
        {
            "zone_id": "shifting_labyrinth",
            "theme": "Ever-changing stone corridors",
            "danger_level": "random",
            "max_npcs": 0,
            "audio_mode": "generate",
        }
    )
    gen_cfg = normalize_dynamic_generation({"max_npcs": 4})
    long_placeholder = build_dynamic_placeholder_scene_id(
        "quiet_meadow_sanctuary_with_very_long_name",
        depth=1,
        index=1,
        suffix="abcd",
    )

    # Assert
    assert peaceful_zone is not None
    assert peaceful_zone["danger_level"] == "peaceful"
    assert peaceful_zone["max_npcs"] == 5
    assert peaceful_zone["audio_mode"] == "empty"
    assert random_zone is not None
    assert random_zone["danger_level"] == "random"
    assert random_zone["max_npcs"] == 0
    assert random_zone["audio_mode"] == "generate"
    assert gen_cfg["max_npcs"] == 4
    assert len(long_placeholder) <= 20
    assert long_placeholder.startswith("DYN_")
    assert long_placeholder.startswith("DYN_")


@pytest.mark.asyncio
async def test_configure_scene_audio_respects_per_exit_override(db_session) -> None:
    """Per-exit audio_mode overrides the global dynamic_generation.audio_mode setting."""
    # Arrange
    from backend.api.routes.adventures import dynamic_scene_media

    del db_session
    origin = WorldScene(
        id="ORIGIN_HUB",
        template_id="adv_audio",
        session_id=None,
        label="Origin Hub",
        description="Warm tavern.",
        audio_track_id="TRACK_TAVERN",
    )
    adv = AdventureTemplate(id="adv_audio", owner_id="u1", title="Audio Test")
    state = SessionState(
        session_id="s_audio",
        template_id="adv_audio",
        user_id="u1",
        avatar_id="a1",
        current_scene_id="ORIGIN_HUB",
        entity_states={},
    )

    # Act: global wants "generate", but exit overrides to "empty"
    empty_track = dynamic_scene_media.configure_scene_audio(
        state=state,
        dyn_cfg={"audio_mode": "generate"},
        origin_scene=origin,
        target_id="DYN_AUDIO_D1_1",
        zone={"zone_id": "audio", "theme": "Echoing cave", "audio_mode": "empty"},
        payload=DynamicGeneratedScenePayload(name="Silent Tunnel", description="Quiet."),
        adventure=adv,
    )
    assert empty_track is None
    assert (state.entity_states or {}).get("_dynamic_audio_tracks") is None

    # Act: global wants "empty", but exit overrides to "inherit"
    inherited_track = dynamic_scene_media.configure_scene_audio(
        state=state,
        dyn_cfg={"audio_mode": "empty"},
        origin_scene=origin,
        target_id="DYN_AUDIO_D1_2",
        zone={"zone_id": "audio", "theme": "Warm side room", "audio_mode": "inherit"},
        payload=DynamicGeneratedScenePayload(name="Side Room", description="Cozy."),
        adventure=adv,
    )

    # Assert
    assert inherited_track == "TRACK_TAVERN"


@pytest.mark.asyncio
async def test_generate_dynamic_scene_payload_enforces_max_npcs_and_peaceful(
    monkeypatch, db_session
) -> None:
    """generate_dynamic_scene_payload enforces max_npcs cap and converts peaceful hostile NPCs."""

    # Arrange
    class _FakePayloadLLM:
        def __init__(self, *args, **kwargs):
            del args, kwargs

        async def aexecute_complex_task(self, *args, **kwargs):
            del args, kwargs
            return DynamicGeneratedScenePayload(
                name="Herb Garden",
                description="Quiet cloister garden.",
                npcs=[
                    DynamicGeneratedNpc(
                        id="MONK_A",
                        name="Brother Anselm",
                        description="Tends rosemary beds.",
                        attitude="hostile",
                        combat_role="boss",
                    ),
                    DynamicGeneratedNpc(
                        id="MONK_B",
                        name="Sister Clara",
                        description="Waters lavender.",
                        attitude="friendly",
                        combat_role="none",
                    ),
                ],
            )

    monkeypatch.setattr(dynamic_scene_generator, "GameMasterLLM", _FakePayloadLLM)
    monkeypatch.setattr(dynamic_scene_generator, "_has_provider_credentials", lambda *_: True)
    monkeypatch.setattr(
        dynamic_scene_generator,
        "roll_scene_plan",
        lambda zone, cap, **_: {
            "target_npcs": 1 if cap > 0 else 0,
            "target_objects": 0,
            "allow_container": False,
            "allow_switch": False,
            "allowed_item_types": ["STANDARD", "CONSUMABLE", "READABLE"],
        },
    )

    user = User(
        id=str(uuid.uuid4()),
        username=f"peaceful_tester_{uuid.uuid4().hex[:8]}",
        hashed_password="x",
    )

    # Act: max_npcs=1 with danger_level='peaceful'
    payload_one = await dynamic_scene_generator.generate_dynamic_scene_payload(
        adventure_title="Abbey",
        adventure_setting="Mountain monastery",
        adventure_tone="Serene",
        origin_scene_name="Cloister",
        origin_scene_description="Quiet stone cloister.",
        exit_label="Garden Gate",
        dynamic_zone={
            "zone_id": "abbey_garden",
            "theme": "Tranquil herb garden",
            "max_depth": 2,
            "danger_level": "peaceful",
            "max_npcs": 1,
        },
        language="English",
        user=user,
        db=db_session,
    )
    payload_zero = await dynamic_scene_generator.generate_dynamic_scene_payload(
        adventure_title="Abbey",
        adventure_setting="Mountain monastery",
        adventure_tone="Serene",
        origin_scene_name="Cloister",
        origin_scene_description="Quiet stone cloister.",
        exit_label="Garden Gate",
        dynamic_zone={
            "zone_id": "abbey_garden",
            "theme": "Tranquil herb garden",
            "max_depth": 2,
            "danger_level": "peaceful",
            "max_npcs": 0,
        },
        language="English",
        user=user,
        db=db_session,
    )

    # Assert
    assert len(payload_one.npcs) == 1
    assert payload_one.npcs[0].attitude == "neutral"
    assert payload_one.npcs[0].combat_role == "none"
    assert payload_zero.npcs == []


@pytest.mark.asyncio
async def test_blueprint_and_editor_strip_and_block_virtual_dynamic_scenes(db_session) -> None:
    """Virtual DYN_* placeholder scenes are stripped on manifest apply and rejected in editor CRUD."""
    # Arrange
    from fastapi import HTTPException

    from backend.api.routes.adventures.editing.payload import _build_adventure_editor_assets
    from backend.api.routes.adventures.editing.schemas import (
        SceneCreateRequest,
        StartSceneUpdateRequest,
    )
    from backend.api.routes.adventures.editing.world_crud import (
        create_editor_scene,
        update_editor_start_scene,
    )
    from backend.engine.manifest_apply import apply_manifest

    bp_text = """[World]
title: Test World
dynamic_max_npcs: 1

[Scene: HUB] Central Square

[Exit: HUB -> MINES] a dark mine shaft
theme: Flooded iron mines
danger: random
max_npcs: 1
audio: empty
"""
    manifest = {
        "adventure": {"title": "Test World", "start_scene_id": "HUB"},
        "protagonist": {"name": "Hero"},
        "scenes": [
            {"id": "HUB", "label": "Central Square", "description": "Town square."},
            {"id": "DYN_MINES_D1_1", "label": "", "description": ""},
        ],
        "exits": [
            {
                "from_scene_id": "HUB",
                "to_scene_id": "DYN_MINES_D1_1",
                "label": "a dark mine shaft",
                "dynamic_zone": {
                    "enabled": True,
                    "zone_id": "mines",
                    "theme": "Flooded iron mines",
                    "danger_level": "random",
                    "max_npcs": 1,
                    "audio_mode": "empty",
                },
            }
        ],
    }

    # Act: blueprint merge strips fabricated DYN_* scene
    parsed, _issues = analyze_blueprint(bp_text)
    apply_blueprint(manifest, parsed)
    merged_ids = {s["id"] for s in manifest["scenes"]}
    assert "HUB" in merged_ids
    assert "DYN_MINES_D1_1" not in merged_ids

    # Re-inject a fabricated DYN_* scene to verify apply_manifest also skips persisting it
    manifest["scenes"].append({"id": "DYN_MINES_D1_1", "label": "", "description": ""})

    # Act: apply_manifest persists HUB + dynamic exit without creating DYN_MINES_D1_1 WorldScene
    user = User(id="u_guard", username=f"guard_{uuid.uuid4().hex[:6]}", hashed_password="x")
    adv = AdventureTemplate(
        id="adv_dyn_guard",
        owner_id=user.id,
        title="Guard Test",
    )
    db_session.add_all([user, adv])
    await db_session.commit()

    await apply_manifest(db_session, adv.id, manifest, user=user)
    await db_session.commit()

    persisted_scenes = (
        await db_session.scalars(
            select(WorldScene).where(
                WorldScene.template_id == adv.id,
                WorldScene.session_id.is_(None),
            )
        )
    ).all()
    assert [s.id for s in persisted_scenes] == ["HUB"]

    # Stray DB DYN_* scene (e.g. legacy adventure) is hidden from editor assets payload
    db_session.add(
        WorldScene(
            id="DYN_LEGACY_D1_1",
            template_id=adv.id,
            session_id=None,
            label="",
            description="",
        )
    )
    await db_session.commit()
    payload = await _build_adventure_editor_assets(adv.id, db_session)
    assert [s["id"] for s in payload.scenes] == ["HUB"]

    # Editor create/start-scene endpoints reject DYN_* IDs
    with pytest.raises(HTTPException) as create_exc:
        await create_editor_scene(
            adv.id,
            SceneCreateRequest(scene_id="DYN_FAKE", label="Fake", description="Fake scene."),
            db=db_session,
            current_user=user,
        )
    assert create_exc.value.status_code == 400

    with pytest.raises(HTTPException) as start_exc:
        await update_editor_start_scene(
            adv.id,
            StartSceneUpdateRequest(scene_id="DYN_LEGACY_D1_1"),
            db=db_session,
            current_user=user,
        )
    assert start_exc.value.status_code == 400


@pytest.mark.asyncio
async def test_roll_scene_plan_and_object_variety_enforcement(monkeypatch, db_session) -> None:
    """roll_scene_plan allows 0 NPCs, limits switches/containers, and _build_* initializes metadata."""
    # Arrange
    zone = normalize_dynamic_zone(
        {
            "zone_id": "frost_caves",
            "theme": "Glacial ice caverns",
            "depth": 1,
            "max_depth": 3,
            "max_npcs": 2,
        }
    )
    assert zone is not None

    # Deterministic roll: 0 NPCs (0.60 >= 0.55), 2 objects (0.60 < 0.75), no container/switch
    monkeypatch.setattr(
        dynamic_scene_generator.random, "randint", lambda a, b: 0 if a == 0 and b == 2 else 2
    )
    monkeypatch.setattr(dynamic_scene_generator.random, "random", lambda: 0.60)

    plan = dynamic_scene_generator.roll_scene_plan(zone, max_npcs=2)
    assert plan["target_npcs"] == 0
    assert plan["allow_container"] is False
    assert plan["allow_switch"] is False

    class _OverstuffedPayloadLLM:
        def __init__(self, *args, **kwargs):
            del args, kwargs

        async def aexecute_complex_task(self, *args, **kwargs):
            del args, kwargs
            return DynamicGeneratedScenePayload(
                name="Glacial Hollow",
                description="Wind whistles through empty blue ice.",
                npcs=[
                    DynamicGeneratedNpc(
                        id="STRAY",
                        name="Stray Guide",
                        npc_type="HUMANOID",
                        description="Wanders the ridge.",
                    )
                ],
                objects=[
                    DynamicGeneratedObject(
                        id="CRATE",
                        name="Supply Cache",
                        item_type="CONTAINER",
                        description="An old cache.",
                    ),
                    DynamicGeneratedObject(
                        id="LEVER",
                        name="Ice Valve",
                        item_type="SWITCH",
                        description="A frozen valve.",
                    ),
                ],
            )

    monkeypatch.setattr(dynamic_scene_generator, "GameMasterLLM", _OverstuffedPayloadLLM)
    monkeypatch.setattr(dynamic_scene_generator, "_has_provider_credentials", lambda *_: True)

    user = User(
        id=str(uuid.uuid4()),
        username=f"variety_tester_{uuid.uuid4().hex[:8]}",
        hashed_password="x",
    )

    # Act
    payload = await dynamic_scene_generator.generate_dynamic_scene_payload(
        adventure_title="Frost",
        adventure_setting="Frozen North",
        adventure_tone="Stark",
        origin_scene_name="Ridge",
        origin_scene_description="Windy ridge.",
        exit_label="Crevasse",
        dynamic_zone=zone,
        language="English",
        user=user,
        db=db_session,
    )

    # Assert: 0 NPCs enforced and unrolled CONTAINER/SWITCH coerced to STANDARD
    assert payload.npcs == []
    assert [obj.item_type for obj in payload.objects] == ["STANDARD", "STANDARD"]

    # Entity builders preserve npc_type, intelligible speech note, and SWITCH defaults
    state = SessionState(
        session_id="s_var",
        template_id="adv_var",
        user_id=user.id,
        avatar_id="av_var",
        current_scene_id="DYN_FROST_D1_1",
        entity_states={},
    )
    npc_ent = dynamic_scene_flow._build_npc_entity(
        session_id="s_var",
        target_id="DYN_FROST_D1_1",
        npc=DynamicGeneratedNpc(
            id="SCOUT",
            name="Outsider Scout",
            npc_type="ANIMAL",
            description="A white fox.",
            dialogue_style="Silent watcher",
        ),
        image_url=None,
        state=state,
    )
    human_ent = dynamic_scene_flow._build_npc_entity(
        session_id="s_var",
        target_id="DYN_FROST_D1_1",
        npc=DynamicGeneratedNpc(
            id="TRADER",
            name="Valley Trader",
            npc_type="HUMANOID",
            description="Carries salt and pelts.",
            dialogue_style="Warm and practical",
        ),
        image_url=None,
        state=state,
    )
    switch_ent = dynamic_scene_flow._build_object_entity(
        session_id="s_var",
        target_id="DYN_FROST_D1_1",
        obj=DynamicGeneratedObject(
            id="SLUICE",
            name="Frozen Sluice Gate",
            item_type="SWITCH",
            description="Controls meltwater flow.",
            is_takeable=False,
        ),
    )

    assert npc_ent.npc_type == "ANIMAL"
    assert human_ent.npc_type == "HUMANOID"
    assert "full sentences" in (human_ent.character or "").lower()
    assert (switch_ent.metadata_json or {}).get("switch_states") == ["OFF", "ON"]
    assert (switch_ent.metadata_json or {}).get("switch_initial_state") == "OFF"


@pytest.mark.asyncio
async def test_script_teleport_dynamic_inline_materializes_scene(db_session, monkeypatch) -> None:
    """tw.scene.teleport_dynamic materializes a procedural scene on trigger and honors return_exit/fresh."""
    from backend.engine.interaction.trigger_service import TriggerService

    # Arrange
    _, adv, state, _, _ = await _seed_dynamic_session(db_session)
    calls: list[dict] = []

    async def _fake_payload(**kwargs):
        calls.append(kwargs["dynamic_zone"])
        return DynamicGeneratedScenePayload(
            name="Astral Nexus",
            description="Floating obelisks drift over a mirror-still void.",
            visual_description="Floating stone obelisks in violet starlight",
            npcs=[],
            objects=[],
            forward_exits=[],
        )

    monkeypatch.setattr(dynamic_scene_flow, "generate_dynamic_scene_payload", _fake_payload)

    script = (
        'dest = tw.scene.teleport_dynamic("Shifting astral nexus", '
        'danger_level="peaceful", max_npcs=0, return_exit=False, label="Astral Pad")\n'
        'tw.vars.set("last_dest", dest)\n'
    )

    # Act
    await TriggerService.execute_trigger(
        db_session,
        state,
        trigger_name="on_interact",
        target_id="TELEPORTER_PAD",
        script_code=script,
        narrative_text="",
    )
    await db_session.commit()

    # Assert: materialized inline dynamic scene and omitted return exit
    first_dest = state.current_scene_id
    assert first_dest.startswith("DYN_")
    assert len(first_dest) <= 20
    assert all(ch.isupper() or ch.isdigit() or ch == "_" for ch in first_dest)
    assert (state.entity_states or {}).get("__script_vars__", {}).get("last_dest") == first_dest
    assert calls[0]["danger_level"] == "peaceful"
    assert calls[0]["max_npcs"] == 0

    scene_row = (
        (
            await db_session.execute(
                select(WorldScene).where(
                    WorldScene.session_id == state.session_id,
                    WorldScene.id == first_dest,
                )
            )
        )
        .scalars()
        .first()
    )
    assert scene_row is not None
    assert scene_row.label == "Astral Nexus"

    return_exits = (
        (
            await db_session.execute(
                select(WorldExit).where(
                    WorldExit.session_id == state.session_id,
                    WorldExit.from_scene_id == first_dest,
                )
            )
        )
        .scalars()
        .all()
    )
    assert return_exits == []

    # Act again with fresh=True -> generates a distinct scene ID
    state.current_scene_id = "TOWN_GATE"
    fresh_script = (
        'tw.scene.teleport_dynamic("Shifting astral nexus", '
        'danger_level="peaceful", max_npcs=0, return_exit=True, label="Astral Pad", fresh=True)'
    )
    await TriggerService.execute_trigger(
        db_session,
        state,
        trigger_name="on_interact",
        target_id="TELEPORTER_PAD",
        script_code=fresh_script,
        narrative_text="",
    )
    await db_session.commit()

    assert state.current_scene_id != first_dest
    fresh_return = (
        (
            await db_session.execute(
                select(WorldExit).where(
                    WorldExit.session_id == state.session_id,
                    WorldExit.from_scene_id == state.current_scene_id,
                    WorldExit.to_scene_id == "TOWN_GATE",
                )
            )
        )
        .scalars()
        .first()
    )
    assert fresh_return is not None


@pytest.mark.asyncio
async def test_script_teleport_existing_dynamic_exit_placeholder(db_session, monkeypatch) -> None:
    """tw.scene.teleport materializes an unmaterialized dynamic exit placeholder and sets return exit."""
    from backend.api.routes.adventures.dynamic_teleport import apply_script_teleport
    from backend.engine.scripting.context import GameContext

    # Arrange
    _, adv, state, _, _ = await _seed_dynamic_session(db_session)

    async def _fake_payload(**kwargs):
        return DynamicGeneratedScenePayload(
            name="Flooded Lift Shaft",
            description="Dark water laps against rusted iron rails.",
            visual_description="Flooded mine shaft",
            npcs=[],
            objects=[],
            forward_exits=[],
        )

    monkeypatch.setattr(dynamic_scene_flow, "generate_dynamic_scene_payload", _fake_payload)

    ctx = GameContext(
        avatar_data={},
        current_scene_id="TOWN_GATE",
        entities={},
    )
    ctx.scene.teleport("DYN_IRON_MINES_D1_1")

    # Act
    new_scene = await apply_script_teleport(
        db_session,
        state,
        ctx.changeset,
        adventure=adv,
    )
    await db_session.commit()

    # Assert
    assert new_scene is not None
    assert new_scene.id == "DYN_IRON_MINES_D1_1"
    assert state.current_scene_id == "DYN_IRON_MINES_D1_1"
    return_exit = (
        (
            await db_session.execute(
                select(WorldExit).where(
                    WorldExit.session_id == state.session_id,
                    WorldExit.from_scene_id == "DYN_IRON_MINES_D1_1",
                    WorldExit.to_scene_id == "TOWN_GATE",
                )
            )
        )
        .scalars()
        .first()
    )
    assert return_exit is not None
    assert return_exit.label == "Return to Town Gate"


@pytest.mark.asyncio
async def test_npc_speech_rule_in_narration_context_and_interlude_quotes(
    db_session, monkeypatch
) -> None:
    """Narration location context injects speech rules by npc_type, and quotes exclude ANIMAL/MONSTER."""
    from types import SimpleNamespace

    from backend.engine.interaction.location_context import build_location_context

    # Arrange
    scene = SimpleNamespace(
        id="COURTYARD",
        label="Courtyard",
        description="A misty stone courtyard.",
        decorative_objects=[],
    )
    npcs = [
        SimpleNamespace(
            id="GUARD",
            entity_type="NPC",
            name="Captain Rowan",
            npc_type="HUMANOID",
            character="Gruff but fair",
            goal="Guard the gate",
            description="A veteran watchman.",
            spatial_position="by the archway",
            appearance=None,
            inventory=[],
            hp=100,
            max_hp=100,
            mana=None,
            max_mana=None,
            stamina=None,
            max_stamina=None,
            is_hidden=False,
            is_defeated=False,
            notes=None,
            moveable=False,
            movement_type="STATIONARY",
            allowed_scenes=[],
        ),
        SimpleNamespace(
            id="ORACLE",
            entity_type="NPC",
            name="Starlight Sprite",
            npc_type="BEING",
            character="",
            goal="Watch the sky",
            description="A hovering luminous spirit.",
            spatial_position="above the well",
            appearance=None,
            inventory=[],
            hp=50,
            max_hp=50,
            mana=100,
            max_mana=100,
            stamina=None,
            max_stamina=None,
            is_hidden=False,
            is_defeated=False,
            notes=None,
            moveable=False,
            movement_type="STATIONARY",
            allowed_scenes=[],
        ),
        SimpleNamespace(
            id="WOLF",
            entity_type="NPC",
            name="Ash Fang",
            npc_type="ANIMAL",
            character="Fiercely territorial",
            goal="Defend the den",
            description="A scarred gray wolf.",
            spatial_position="by the pine",
            appearance=None,
            inventory=[],
            hp=60,
            max_hp=60,
            mana=None,
            max_mana=None,
            stamina=None,
            max_stamina=None,
            is_hidden=False,
            is_defeated=False,
            notes=None,
            moveable=False,
            movement_type="STATIONARY",
            allowed_scenes=[],
        ),
    ]

    # Act: full narration context
    narration_ctx = build_location_context(scene, npcs, [], detail_level="full")

    # Assert: all NPCs carry [Type: ...] and matching speech rule
    assert "Captain Rowan (ID: GUARD) [Type: HUMANOID]" in narration_ctx
    assert "Gruff but fair (Speaks in plain, intelligible full sentences.)" in narration_ctx
    assert "Starlight Sprite (ID: ORACLE) [Type: BEING]" in narration_ctx
    assert "Ash Fang (ID: WOLF) [Type: ANIMAL]" in narration_ctx
    assert (
        "Non-verbal creature sounds and body language only; does NOT speak sentences."
        in narration_ctx
    )

    # Act & Assert: interlude quotes skip ANIMAL/MONSTER and return None if no HUMANOID/BEING exists
    monkeypatch.setattr(dynamic_scene_generator, "_has_provider_credentials", lambda *_: True)
    user = User(
        id=str(uuid.uuid4()),
        username=f"quote_filter_{uuid.uuid4().hex[:8]}",
        hashed_password="x",
    )
    only_monsters = [
        {"id": "WOLF", "name": "Ash Fang", "npc_type": "ANIMAL", "is_defeated": False},
        {"id": "GHOUL", "name": "Hollow Stalker", "npc_type": "MONSTER", "is_defeated": False},
    ]
    assert (
        await dynamic_scene_generator.generate_dynamic_interlude_quote(
            adventure_title="Test",
            adventure_setting="Wilds",
            adventure_tone="Tense",
            origin_scene_name="Courtyard",
            exit_label="Trail",
            zone_theme="Deep woods",
            candidate_npcs=only_monsters,
            user=user,
            db=db_session,
        )
        is None
    )

    picked_names: set[str] = set()
    mixed_pool = only_monsters + [
        {"id": "GUARD", "name": "Captain Rowan", "npc_type": "HUMANOID", "is_defeated": False},
        {"id": "ORACLE", "name": "Starlight Sprite", "npc_type": "BEING", "is_defeated": False},
    ]
    for _ in range(15):
        picked = dynamic_scene_generator._pick_interlude_npc(mixed_pool)
        assert picked is not None
        picked_names.add(picked["name"])
    assert picked_names <= {"Captain Rowan", "Starlight Sprite"}


def test_dynamic_spawn_chances_caps_and_item_stats() -> None:
    """Verify per-type NPC caps, spawn probabilities, and mixed item stat persistence."""
    from backend.api.routes.adventures.dynamic_scene_flow import _build_object_entity
    from backend.engine.world.dynamic_scene_plan import (
        apply_scene_plan_to_payload,
        roll_scene_plan,
    )
    from backend.engine.world.dynamic_scene_schemas import (
        DynamicGeneratedScenePayload,
        normalize_dynamic_generation,
        normalize_dynamic_zone,
        resolve_effective_dynamic_rules,
    )

    gen_cfg = normalize_dynamic_generation(
        {
            "npc_type_caps": {"humanoid": 1, "being": 0, "animal": 2, "monster": 0},
            "spawn_chances": {"npc": 100, "enemy": 0, "item": 100, "container": 0, "switch": 0},
        }
    )
    zone = normalize_dynamic_zone(
        {
            "zone_id": "quiet_chapel",
            "theme": "Silent stone chapel",
            "max_npcs": 3,
            "spawn_chances": {"npc": 0},
        }
    )
    assert zone is not None

    caps, chances = resolve_effective_dynamic_rules(zone, gen_cfg)
    assert caps == {"humanoid": 1, "being": 0, "animal": 2, "monster": 0}
    assert chances["npc"] == 0
    assert chances["enemy"] == 0
    assert chances["item"] == 100

    silent_plan = roll_scene_plan(zone, max_npcs=3, generation_config=gen_cfg)
    assert silent_plan["target_npcs"] == 0
    assert silent_plan["npc_slots"] == []
    assert silent_plan["allow_container"] is False
    assert silent_plan["allow_switch"] is False
    assert silent_plan["target_objects"] >= 1

    payload = DynamicGeneratedScenePayload.model_validate(
        {
            "name": "Chapel Nave",
            "description": "Dust motes drift in silence.",
            "npcs": [
                {
                    "id": "HERMIT",
                    "name": "Brother Ivo",
                    "npc_type": "HUMANOID",
                    "description": "Quiet caretaker.",
                    "attitude": "hostile",
                },
                {
                    "id": "GHOST",
                    "name": "Wisp",
                    "npc_type": "BEING",
                    "description": "Should be dropped by cap=0.",
                },
            ],
            "objects": [
                {
                    "id": "RING_GRACE",
                    "name": "Silver Ring",
                    "item_type": "WEARABLE",
                    "description": "A tarnished ring.",
                },
                {
                    "id": "TONIC",
                    "name": "Herbal Tonic",
                    "item_type": "CONSUMABLE",
                    "description": "Bitter brew.",
                },
                {
                    "id": "DAGGER",
                    "name": "Iron Dagger",
                    "item_type": "WEAPON",
                    "description": "Simple blade.",
                },
                {
                    "id": "PEBBLE",
                    "name": "Smooth Pebble",
                    "item_type": "STANDARD",
                    "description": "Just a flavor trinket.",
                },
            ],
        }
    )
    apply_scene_plan_to_payload(
        payload,
        {
            "target_npcs": 2,
            "npc_type_caps": {"humanoid": 1, "being": 0, "animal": 2, "monster": 0},
            "allow_hostile": False,
            "target_objects": 4,
            "allow_container": False,
            "allow_switch": False,
        },
    )
    assert [n.id for n in payload.npcs] == ["HERMIT"]
    assert payload.npcs[0].attitude == "neutral"
    assert payload.npcs[0].combat_role == "none"

    ring, tonic, dagger, pebble = payload.objects
    assert ring.wearable_slots
    assert any(
        getattr(ring, attr) != 0
        for attr in (
            "stat_modifier_strength",
            "stat_modifier_dexterity",
            "stat_modifier_intelligence",
            "stat_modifier_wisdom",
            "stat_modifier_charisma",
            "stat_modifier_armor_class",
        )
    )
    assert tonic.hp_change > 0
    assert dagger.damage_dice == "1d6"
    assert pebble.stat_modifier_strength == 0 and pebble.hp_change == 0

    ring_entity = _build_object_entity(
        session_id="sess-1", target_id="DYN_QUIET_CHAPEL_D1_1", obj=ring
    )
    assert ring_entity.is_portable is True
    assert ring_entity.wearable_slots == ring.wearable_slots
    tonic_entity = _build_object_entity(
        session_id="sess-1", target_id="DYN_QUIET_CHAPEL_D1_1", obj=tonic
    )
    assert tonic_entity.metadata_json.get("hp_change") == tonic.hp_change


@pytest.mark.asyncio
async def test_after_generated_script_inspects_and_populates_scene(monkeypatch, db_session) -> None:
    """on_after_generated_script receives generated_scene data and can add items/NPCs."""
    user = User(
        id=str(uuid.uuid4()),
        username=f"after_gen_{uuid.uuid4().hex[:8]}",
        hashed_password="x",
    )
    adv_id = str(uuid.uuid4())
    adv = AdventureTemplate(
        id=adv_id,
        title="Trigger Ruin",
        owner_id=user.id,
        language="English",
        dynamic_generation={
            "scene_image_mode": "off",
            "npc_image_mode": "off",
            "item_image_mode": "off",
        },
    )
    session_id = str(uuid.uuid4())
    avatar_id = str(uuid.uuid4())
    avatar = Avatar(id=avatar_id, user_id=user.id, template_id=adv_id, name="Tester")
    gs = GameSession(id=session_id, template_id=adv_id, user_id=user.id, avatar_id=avatar_id)
    state = SessionState(
        session_id=session_id,
        template_id=adv_id,
        user_id=user.id,
        avatar_id=avatar_id,
        current_scene_id="START",
        entity_states={},
    )
    origin_scene = WorldScene(
        id="START",
        session_id=session_id,
        label="Ruins Gate",
        description="A stone archway.",
    )
    # Template entities in another scene to clone into the newly generated scene
    bonus_item = WorldEntity(
        id="RELIC_KEY",
        session_id=session_id,
        entity_type="OBJECT",
        name="Relic Key",
        description="An ornate bronze key.",
        current_scene_id="VAULT_TEMPLATE",
        item_type="STANDARD",
        is_portable=True,
        inventory=[],
        metadata_json={},
    )
    bonus_npc = WorldEntity(
        id="SCOUT_ALLY",
        session_id=session_id,
        entity_type="NPC",
        name="Scout Lyra",
        description="A friendly scout.",
        current_scene_id="VAULT_TEMPLATE",
        npc_type="HUMANOID",
        inventory=[],
        metadata_json={},
    )
    after_script = (
        'tw.vars.set("seen_name", generated_scene["name"])\n'
        'tw.vars.set("seen_npc_count", len(tw.generated_scene["npcs"]))\n'
        'if generated_scene["depth"] == 1:\n'
        '    tw.items.clone("RELIC_KEY", scene_id=generated_scene["id"])\n'
        '    tw.npcs.clone("SCOUT_ALLY", scene_id=generated_scene["id"])\n'
    )
    dyn_exit = WorldExit(
        session_id=session_id,
        from_scene_id="START",
        to_scene_id="DYN_CRYPT_D1_1",
        label="Descend into Crypt",
        exit_type="bidirectional",
        dynamic_zone={
            "enabled": True,
            "zone_id": "crypt",
            "theme": "Ancient flooded crypt",
            "depth": 1,
            "max_depth": 2,
            "danger_level": "low",
            "max_npcs": 1,
            "on_after_generated_script": after_script,
        },
    )
    db_session.add_all(
        [user, adv, gs, avatar, state, origin_scene, bonus_item, bonus_npc, dyn_exit]
    )
    await db_session.flush()

    async def _fake_generate_payload(**kwargs):
        del kwargs
        return DynamicGeneratedScenePayload(
            name="Flooded Vestibule",
            description="Cold water laps against mossy pillars.",
            npcs=[
                DynamicGeneratedNpc(
                    id="SHADE",
                    name="Crypt Shade",
                    npc_type="BEING",
                    description="Drifts silently.",
                )
            ],
            objects=[
                DynamicGeneratedObject(
                    id="LANTERN",
                    name="Brass Lantern",
                    item_type="STANDARD",
                    description="Still warm.",
                )
            ],
            forward_exits=[
                DynamicGeneratedChildExit(label="Deeper Stair", theme_hint="Sunken hall")
            ],
        )

    monkeypatch.setattr(
        dynamic_scene_flow, "generate_dynamic_scene_payload", _fake_generate_payload
    )

    new_scene = await dynamic_scene_flow.materialize_dynamic_scene_for_exit(
        db=db_session,
        state=state,
        adventure=adv,
        user=user,
        world_exit=dyn_exit,
        origin_scene=origin_scene,
        language="English",
    )

    assert new_scene.id == "DYN_CRYPT_D1_1"
    script_vars = (state.entity_states or {}).get("__script_vars__", {})
    assert script_vars["seen_name"] == "Flooded Vestibule"
    assert script_vars["seen_npc_count"] == 1

    spawned_rows = (
        (
            await db_session.execute(
                select(WorldEntity).where(
                    WorldEntity.session_id == session_id,
                    WorldEntity.current_scene_id == "DYN_CRYPT_D1_1",
                )
            )
        )
        .scalars()
        .all()
    )
    spawned_names = {row.name for row in spawned_rows}
    assert {"Crypt Shade", "Brass Lantern", "Relic Key", "Scout Lyra"} <= spawned_names


def test_dynamic_placeholder_pseudoname_deterministic_and_bounded() -> None:
    """Placeholder IDs use deterministic pronounceable pseudo-names capped at 20 chars."""
    id_a1 = build_dynamic_placeholder_scene_id("IRON_MINES", depth=1, index=1)
    id_a2 = build_dynamic_placeholder_scene_id("iron_mines", depth=1, index=1)
    id_b = build_dynamic_placeholder_scene_id("iron_mines", depth=1, index=2)
    id_c = build_dynamic_placeholder_scene_id(
        "VERY_LONG_ZONE_IDENTIFIER_THAT_EXCEEDS_LIMIT", depth=3, index=2, suffix="ABCD1234"
    )

    assert id_a1 == id_a2
    assert id_a1 != id_b
    assert id_a1.startswith("DYN_")
    assert "_D1_1_" not in id_a1
    for candidate in (id_a1, id_b, id_c):
        assert 4 <= len(candidate) <= 20
        assert all(ch.isupper() or ch.isdigit() or ch == "_" for ch in candidate)


def test_normalize_dynamic_zone_instructions_and_cluster_consistency() -> None:
    """Dynamic zone normalization retains instructions, root_theme, and cluster_consistency."""
    from backend.engine.world.dynamic_scene_schemas import normalize_dynamic_zone

    defaulted = normalize_dynamic_zone(
        {
            "zone_id": "old_stable",
            "theme": "Drafty stable",
            "instructions": "  Generate a loot chest with a 1d+2 sword  ",
        }
    )
    assert defaulted["instructions"] == "Generate a loot chest with a 1d+2 sword"
    assert defaulted["cluster_consistency"] is True
    assert defaulted["root_theme"] == "Drafty stable"

    disabled = normalize_dynamic_zone(
        {
            "zone_id": "old_stable",
            "theme": "Drafty stable",
            "root_theme": "Country Inn Courtyard",
            "cluster_consistency": False,
        }
    )
    assert disabled["cluster_consistency"] is False
    assert disabled["root_theme"] == "Country Inn Courtyard"


@pytest.mark.asyncio
async def test_loose_instructions_container_and_sword_materialization(
    db_session, monkeypatch
) -> None:
    """Loose instructions drive prompt rules, weapon 1d+2 stats, and container inventory links."""
    from backend.engine.world.dynamic_instructions_helper import (
        adjust_plan_for_instructions,
        apply_instructions_backfill,
        build_instructions_prompt_section,
    )

    user, adv, state, origin_scene, dyn_exit = await _seed_dynamic_session(db_session)
    zone = dict(dyn_exit.dynamic_zone or {})
    zone["instructions"] = "Generate a loot chest in the stable with a 1d+2 sword"
    dyn_exit.dynamic_zone = zone
    await db_session.flush()

    prompt_section = build_instructions_prompt_section(zone)
    assert "Generate a loot chest in the stable with a 1d+2 sword" in prompt_section
    assert "CONTAINER" in prompt_section
    adjusted = adjust_plan_for_instructions(
        {"allow_container": False, "target_objects": 0, "target_npcs": 0},
        zone,
    )
    assert adjusted["allow_container"] is True
    assert adjusted["target_objects"] >= 3

    async def _fake_interlude(**kwargs):
        return None

    async def _fake_scene_payload(**kwargs):
        payload = DynamicGeneratedScenePayload(
            name="Dim Timber Stable",
            description="Hay-strewn stalls smell of rain and leather.",
            npcs=[],
            objects=[
                DynamicGeneratedObject(
                    id="STABLE_CHEST",
                    name="Stable Loot Chest",
                    item_type="CONTAINER",
                    description="An iron-strapped chest under the hayloft ladder.",
                    inventory=["Iron Sword"],
                ),
                DynamicGeneratedObject(
                    id="IRON_SWORD",
                    name="Iron Sword",
                    item_type="WEAPON",
                    description="A keen arming sword wrapped in oiled cloth.",
                    damage_dice="1d+2",
                ),
            ],
            forward_exits=[],
        )
        apply_instructions_backfill(
            payload,
            kwargs["dynamic_zone"],
            {},
            kwargs.get("cluster_context"),
        )
        return payload

    monkeypatch.setattr(dynamic_scene_flow, "generate_dynamic_interlude_quote", _fake_interlude)
    monkeypatch.setattr(dynamic_scene_flow, "generate_dynamic_scene_payload", _fake_scene_payload)

    new_scene = await materialize_dynamic_scene_for_exit(
        db=db_session,
        state=state,
        adventure=adv,
        user=user,
        world_exit=dyn_exit,
        origin_scene=origin_scene,
    )
    await db_session.commit()

    rows = (
        (
            await db_session.execute(
                select(WorldEntity).where(
                    WorldEntity.session_id == state.session_id,
                    WorldEntity.current_scene_id == new_scene.id,
                )
            )
        )
        .scalars()
        .all()
    )
    containers = [row for row in rows if row.item_type == "CONTAINER"]
    weapons = [row for row in rows if row.item_type == "WEAPON"]
    assert len(containers) == 1
    assert len(weapons) == 1
    weapon_meta = weapons[0].metadata_json or {}
    assert weapon_meta.get("damage_dice") == "1d+2"
    assert weapons[0].id in (containers[0].inventory or [])


@pytest.mark.asyncio
async def test_blueprint_instructions_container_and_weapon_backfill(
    db_session, monkeypatch
) -> None:
    """Blueprint tags inside exit instructions create typed entities and link inventories."""
    from backend.engine.world.dynamic_instructions_helper import apply_instructions_backfill

    user, adv, state, origin_scene, dyn_exit = await _seed_dynamic_session(db_session)
    dyn_exit.dynamic_zone = {
        **(dyn_exit.dynamic_zone or {}),
        "instructions": (
            "[Container: iron_chest] Ironbound Chest\n"
            "Heavy bolted chest.\n\n"
            "[Weapon: oak_sword] Rune Sabre\n"
            "location: iron_chest\n"
            "damage_dice: 1d+2"
        ),
    }
    await db_session.flush()

    async def _fake_interlude(**kwargs):
        return None

    async def _fake_scene_payload(**kwargs):
        payload = DynamicGeneratedScenePayload(
            name="Guard Tack Room",
            description="Saddles and oilskin cloaks hang along rough beams.",
            npcs=[],
            objects=[],
            forward_exits=[],
        )
        apply_instructions_backfill(
            payload,
            kwargs["dynamic_zone"],
            {},
            kwargs.get("cluster_context"),
        )
        return payload

    monkeypatch.setattr(dynamic_scene_flow, "generate_dynamic_interlude_quote", _fake_interlude)
    monkeypatch.setattr(dynamic_scene_flow, "generate_dynamic_scene_payload", _fake_scene_payload)

    new_scene = await materialize_dynamic_scene_for_exit(
        db=db_session,
        state=state,
        adventure=adv,
        user=user,
        world_exit=dyn_exit,
        origin_scene=origin_scene,
    )
    await db_session.commit()

    rows = (
        (
            await db_session.execute(
                select(WorldEntity).where(
                    WorldEntity.session_id == state.session_id,
                    WorldEntity.current_scene_id == new_scene.id,
                )
            )
        )
        .scalars()
        .all()
    )
    by_name = {row.name: row for row in rows}
    assert "Ironbound Chest" in by_name
    assert "Rune Sabre" in by_name
    chest = by_name["Ironbound Chest"]
    sabre = by_name["Rune Sabre"]
    assert chest.item_type == "CONTAINER"
    assert sabre.item_type == "WEAPON"
    assert (sabre.metadata_json or {}).get("damage_dice") == "1d+2"
    assert sabre.id in (chest.inventory or [])


@pytest.mark.asyncio
async def test_cluster_consistency_collects_cluster_context_and_respects_toggle(
    db_session, monkeypatch
) -> None:
    """Cluster consistency loads sibling scenes/NPCs/items and obeys toggle off."""
    user, adv, state, origin_scene, dyn_exit = await _seed_dynamic_session(db_session)
    seen_cluster_contexts: list[object] = []

    async def _fake_interlude(**kwargs):
        return None

    async def _fake_scene_payload(**kwargs):
        seen_cluster_contexts.append(kwargs.get("cluster_context"))
        depth = kwargs["dynamic_zone"]["depth"]
        return DynamicGeneratedScenePayload(
            name=f"Cluster Gallery {depth}",
            description="Torchlit stone gallery carved beneath the tavern.",
            npcs=[
                DynamicGeneratedNpc(
                    id=f"MINER_D{depth}",
                    name=f"Miner D{depth}",
                    role="Prospect",
                    description="Works the seam.",
                )
            ],
            objects=[
                DynamicGeneratedObject(
                    id=f"PICK_D{depth}",
                    name=f"Steel Pick {depth}",
                    item_type="STANDARD",
                    description="Chipped but sturdy.",
                )
            ],
            forward_exits=[
                DynamicGeneratedChildExit(label="Lower Seam", theme_hint="Deep basalt vault")
            ]
            if depth < 2
            else [],
        )

    monkeypatch.setattr(dynamic_scene_flow, "generate_dynamic_interlude_quote", _fake_interlude)
    monkeypatch.setattr(dynamic_scene_flow, "generate_dynamic_scene_payload", _fake_scene_payload)

    # First materialization: cluster is initially empty, creates child exit with root_theme
    scene_d1 = await materialize_dynamic_scene_for_exit(
        db=db_session,
        state=state,
        adventure=adv,
        user=user,
        world_exit=dyn_exit,
        origin_scene=origin_scene,
    )
    await db_session.commit()

    assert seen_cluster_contexts[0] == []
    child_exit = (
        (
            await db_session.execute(
                select(WorldExit).where(
                    WorldExit.session_id == state.session_id,
                    WorldExit.from_scene_id == scene_d1.id,
                    WorldExit.to_scene_id != origin_scene.id,
                )
            )
        )
        .scalars()
        .first()
    )
    assert child_exit is not None
    assert child_exit.dynamic_zone["root_theme"] == dyn_exit.dynamic_zone["theme"]

    # Second materialization with cluster_consistency=True sees scene_d1, its NPC and item
    await materialize_dynamic_scene_for_exit(
        db=db_session,
        state=state,
        adventure=adv,
        user=user,
        world_exit=child_exit,
        origin_scene=scene_d1,
    )
    await db_session.commit()

    second_context = seen_cluster_contexts[1]
    assert isinstance(second_context, list)
    assert len(second_context) == 1
    assert second_context[0]["scene_id"] == scene_d1.id
    assert any(n["name"] == "Miner D1" for n in second_context[0]["npcs"])
    assert any(o["name"] == "Steel Pick 1" for o in second_context[0]["objects"])

    # With cluster_consistency=False on a new exit, generator receives empty cluster context
    third_placeholder = build_dynamic_placeholder_scene_id("iron_mines", depth=2, index=2)
    off_exit = WorldExit(
        id="EXIT_OFF_TEST",
        session_id=state.session_id,
        from_scene_id=scene_d1.id,
        to_scene_id=third_placeholder,
        label="Dry Tunnel",
        exit_type="one_way",
        is_revealed=True,
        dynamic_zone={
            "zone_id": "iron_mines",
            "theme": "Dry slate crevice",
            "root_theme": dyn_exit.dynamic_zone["theme"],
            "depth": 2,
            "max_depth": 3,
            "cluster_consistency": False,
        },
    )
    db_session.add(off_exit)
    await db_session.flush()

    await materialize_dynamic_scene_for_exit(
        db=db_session,
        state=state,
        adventure=adv,
        user=user,
        world_exit=off_exit,
        origin_scene=scene_d1,
    )
    assert seen_cluster_contexts[2] is None


def test_cluster_consistency_prompt_formatting_respects_toggle() -> None:
    """Cluster consistency formats themes/scenes/NPCs/items when enabled and omits when off."""
    from backend.engine.world.dynamic_instructions_helper import (
        build_cluster_consistency_prompt_section,
    )

    zone_on = {
        "theme": "Flooded Lower Tunnel",
        "root_theme": "Abandoned Dwarven Iron Mines",
        "cluster_consistency": True,
    }
    cluster = [
        {
            "scene_id": "DYN_TEST_ONE",
            "name": "Collapsed Ore Bay",
            "depth": 1,
            "description": "Rusted rails vanish under dark water.",
            "npcs": [{"name": "Old Borin", "npc_type": "HUMANOID"}],
            "objects": [
                {
                    "name": "Dwarven Pick",
                    "item_type": "WEAPON",
                    "damage_dice": "1d+2",
                    "in_container": "Tool Chest",
                }
            ],
        }
    ]

    text_on = build_cluster_consistency_prompt_section(zone_on, cluster)
    assert "Abandoned Dwarven Iron Mines" in text_on
    assert "Flooded Lower Tunnel" in text_on
    assert "Collapsed Ore Bay" in text_on
    assert "Old Borin" in text_on
    assert "Dwarven Pick" in text_on
    assert "1d+2" in text_on
    assert "Tool Chest" in text_on

    zone_off = {**zone_on, "cluster_consistency": False}
    text_off = build_cluster_consistency_prompt_section(zone_off, cluster)
    assert "Collapsed Ore Bay" not in text_off
    assert "Old Borin" not in text_off


@pytest.mark.asyncio
async def test_instructions_scope_controls_cluster_expansion(db_session, monkeypatch) -> None:
    """Freeform instructions honor scope ('once', 'first_scene', 'max_depth', 'all_scenes')."""
    from backend.engine.world.dynamic_instructions_helper import resolve_active_instructions

    # Arrange: verify scope filtering rules at depth 1 and depth 2
    base_zone = {
        "zone_id": "ruins",
        "theme": "Crumbling stone vaults",
        "instructions": "Generate a loot chest with a 1d+2 sword.",
        "depth": 1,
        "max_depth": 2,
    }
    once_d1, _ = resolve_active_instructions({**base_zone, "instructions_scope": "once"}, [])
    once_d2, _ = resolve_active_instructions(
        {**base_zone, "instructions_scope": "once", "depth": 2}, [{"scene_id": "D1"}]
    )
    max_d1, _ = resolve_active_instructions({**base_zone, "instructions_scope": "max_depth"}, [])
    max_d2, _ = resolve_active_instructions(
        {**base_zone, "instructions_scope": "max_depth", "depth": 2}, [{"scene_id": "D1"}]
    )
    all_d2, _ = resolve_active_instructions(
        {**base_zone, "instructions_scope": "all_scenes", "depth": 2}, [{"scene_id": "D1"}]
    )

    assert "loot chest" in once_d1.lower()
    assert once_d2 == ""
    assert max_d1 == ""
    assert "loot chest" in max_d2.lower()
    assert "loot chest" in all_d2.lower()

    # Act: materialize depth 1 of a 'once' dynamic exit and verify child exit marks instructions_consumed
    user, adv, state, origin_scene, dyn_exit = await _seed_dynamic_session(db_session)
    dyn_exit.dynamic_zone = {
        **dyn_exit.dynamic_zone,
        "instructions": "Generate a loot chest with a bronze key.",
        "instructions_scope": "once",
    }
    await db_session.commit()

    async def _fake_interlude(**kwargs):
        return None

    async def _fake_scene_payload(**kwargs):
        return DynamicGeneratedScenePayload(
            name="Outer Gallery",
            description="Dusty arched chamber.",
            forward_exits=[
                DynamicGeneratedChildExit(label="Deeper Vault", theme_hint="Inner chamber")
            ],
        )

    monkeypatch.setattr(dynamic_scene_flow, "generate_dynamic_interlude_quote", _fake_interlude)
    monkeypatch.setattr(dynamic_scene_flow, "generate_dynamic_scene_payload", _fake_scene_payload)

    scene_d1 = await materialize_dynamic_scene_for_exit(
        db=db_session,
        state=state,
        adventure=adv,
        user=user,
        world_exit=dyn_exit,
        origin_scene=origin_scene,
    )
    child_exit = (
        (
            await db_session.execute(
                select(WorldExit).where(
                    WorldExit.session_id == state.session_id,
                    WorldExit.from_scene_id == scene_d1.id,
                    WorldExit.to_scene_id != origin_scene.id,
                )
            )
        )
        .scalars()
        .first()
    )

    # Assert
    assert child_exit is not None
    child_zone = child_exit.dynamic_zone
    # The deeper room follows its own cluster-blueprint brief; outside its 'once' scope the
    # author text is only story context (no re-spawn) and stays as root_instructions.
    assert child_zone["instructions_source"] == "cluster_blueprint"
    assert "Cluster premise (story context only" in child_zone["instructions"]
    assert child_zone["root_instructions"] == "Generate a loot chest with a bronze key."
    assert child_zone["root_instructions_scope"] == "once"


def test_blueprint_instructions_deduplicate_across_cluster_and_honor_depth() -> None:
    """Blueprint instruction blocks skip already-spawned entities and filter by block depth."""
    from backend.engine.world.dynamic_instructions_helper import (
        apply_instructions_backfill,
        resolve_active_instructions,
    )

    # Arrange
    bp_instructions = (
        "[Container: IRON_CHEST] Loot Chest\n"
        "A bolted iron chest.\n\n"
        "[Weapon: IRON_SWORD] Iron Sword\n"
        "location: IRON_CHEST\n"
        "damage_dice: 1d+2\n\n"
        "[NPC: BOSS_TROLL] Cave Troll\n"
        "depth: max\n"
        "attack: on_sight\n"
    )
    zone_d1 = normalize_dynamic_zone(
        {
            "zone_id": "iron_mines",
            "theme": "Flooded mine",
            "instructions": bp_instructions,
            "instructions_scope": "once",
            "depth": 1,
            "max_depth": 2,
        }
    )

    # Act 1: Depth 1 gets chest + sword, skips BOSS_TROLL (depth: max)
    _, bp_d1 = resolve_active_instructions(zone_d1, [])
    payload_d1 = DynamicGeneratedScenePayload(name="Stables", description="Damp stables.")
    apply_instructions_backfill(payload_d1, zone_d1, {"has_instructions": True}, [])

    assert bp_d1 is not None
    assert [b.ref for b in bp_d1.of_kind("item")] == ["IRON_CHEST", "IRON_SWORD"]
    assert bp_d1.of_kind("npc") == []
    assert [o.id for o in payload_d1.objects] == ["IRON_CHEST", "IRON_SWORD"]
    assert payload_d1.npcs == []

    # Act 2: Depth 2 (max) with IRON_CHEST & IRON_SWORD already in cluster skips duplicates and spawns BOSS_TROLL
    cluster_ctx = [
        {
            "scene_id": "DYN_MINES_1",
            "name": "Stables",
            "depth": 1,
            "npcs": [],
            "objects": [
                {"id": "DYN_MINES_1_IRON_CHEST", "name": "Loot Chest", "item_type": "CONTAINER"},
                {"id": "DYN_MINES_1_IRON_SWORD", "name": "Iron Sword", "item_type": "WEAPON"},
            ],
        }
    ]
    zone_d2 = {**zone_d1, "depth": 2}
    _, bp_d2 = resolve_active_instructions(zone_d2, cluster_ctx)
    payload_d2 = DynamicGeneratedScenePayload(name="Deep Lair", description="Cavern core.")
    apply_instructions_backfill(payload_d2, zone_d2, {"has_instructions": True}, cluster_ctx)

    # Assert
    assert bp_d2 is not None
    assert bp_d2.of_kind("item") == []
    assert [b.ref for b in bp_d2.of_kind("npc")] == ["BOSS_TROLL"]
    assert payload_d2.objects == []
    assert [n.id for n in payload_d2.npcs] == ["BOSS_TROLL"]


@pytest.mark.asyncio
async def test_premapped_dynamic_scene_materializes_preserving_exits_and_entities(
    db_session, monkeypatch
) -> None:
    """Pre-mapped WorldScene.dynamic_zone materializes on entry while keeping exits & static entities."""
    from backend.api.routes.adventures.logic import AdventureLogic

    # Arrange
    user, adv, state, origin_scene, dyn_exit = await _seed_dynamic_session(db_session)
    stable_scene = WorldScene(
        id="PRE_STABLE",
        template_id=adv.id,
        session_id=state.session_id,
        label="Old Stable",
        description="Authored note: stone stable behind the inn.",
        dynamic_zone=normalize_dynamic_zone(
            {
                "zone_id": "haunted_farm",
                "theme": "Cobwebbed stone stable smelling of lantern oil and ash",
                "danger_level": "medium",
                "cluster_consistency": True,
                "on_after_generated_script": "tw.vars.set('premapped_done', generated_scene['id'])",
            }
        ),
    )
    barn_scene = WorldScene(
        id="PRE_BARN",
        template_id=adv.id,
        session_id=state.session_id,
        label="Collapsed Barn",
        description="Timberloft overlooking the yard.",
        dynamic_zone=normalize_dynamic_zone(
            {
                "zone_id": "haunted_farm",
                "theme": "Sagging timber barn overlooking a fogbound courtyard",
                "danger_level": "low",
                "cluster_consistency": True,
            }
        ),
    )
    entry_exit = WorldExit(
        id="EXIT_TO_PRE_STABLE",
        session_id=state.session_id,
        from_scene_id=origin_scene.id,
        to_scene_id="PRE_STABLE",
        label="a crooked stable door",
        exit_type="bidirectional",
    )
    authored_link = WorldExit(
        id="EXIT_STABLE_TO_BARN",
        session_id=state.session_id,
        from_scene_id="PRE_STABLE",
        to_scene_id="PRE_BARN",
        label="a mud-splashed paddock gate",
        exit_type="bidirectional",
    )
    static_marker = WorldEntity(
        id="STATIC_PLAQUE",
        session_id=state.session_id,
        entity_type="OBJECT",
        item_type="READABLE",
        name="Brass Stable Plaque",
        description="Reads: Est. 1842.",
        current_scene_id="PRE_STABLE",
        is_portable=False,
    )
    db_session.add_all([stable_scene, barn_scene, entry_exit, authored_link, static_marker])
    await db_session.commit()

    # Metadata marks both unmaterialized Dynamic Scenes as dynamic + unknown before entry
    meta_before = await AdventureLogic.get_all_scene_metadata(
        db_session, adv.id, session_id=state.session_id
    )
    assert meta_before["PRE_STABLE"]["is_dynamic"] is True
    assert meta_before["PRE_STABLE"]["is_unknown"] is True
    assert meta_before["PRE_BARN"]["is_dynamic"] is True
    assert meta_before["PRE_BARN"]["is_unknown"] is True

    captured_calls: list[dict] = []

    async def _fake_interlude(**kwargs):
        return None

    async def _fake_scene_payload(**kwargs):
        captured_calls.append(
            {
                "cluster_context": kwargs.get("cluster_context"),
                "existing_scene_hint": kwargs.get("existing_scene_hint"),
            }
        )
        scene_id = (kwargs.get("existing_scene_hint") or {}).get("id")
        return DynamicGeneratedScenePayload(
            name=f"Generated {scene_id}",
            description=f"Materialized description for {scene_id}.",
            npcs=[
                DynamicGeneratedNpc(
                    id="STABLE_HAND",
                    name="Pale Groom" if scene_id == "PRE_STABLE" else "Barn Owl Keeper",
                    role="Caretaker",
                    description="Watches the rafters.",
                )
            ],
            objects=[
                DynamicGeneratedObject(
                    id="OIL_LAMP",
                    name="Sooty Lantern",
                    item_type="STANDARD",
                    description="Warm glass lantern.",
                )
            ],
            forward_exits=[DynamicGeneratedChildExit(label="Ignored Exit", theme_hint="Ignored")],
        )

    monkeypatch.setattr(dynamic_scene_flow, "generate_dynamic_interlude_quote", _fake_interlude)
    monkeypatch.setattr(dynamic_scene_flow, "generate_dynamic_scene_payload", _fake_scene_payload)

    # Act 1: Enter PRE_STABLE via authored non-dynamic exit -> materializes in-place
    mat_stable = await materialize_dynamic_scene_for_exit(
        db=db_session,
        state=state,
        adventure=adv,
        user=user,
        world_exit=entry_exit,
        origin_scene=origin_scene,
    )
    await db_session.commit()

    # Assert 1: Existing exits & static item preserved, description & generated entities saved, script fired
    assert mat_stable.id == "PRE_STABLE"
    assert mat_stable.label == "Old Stable"
    assert mat_stable.description == "Materialized description for PRE_STABLE."
    assert mat_stable.dynamic_zone["materialized"] is True
    assert captured_calls[0]["existing_scene_hint"]["id"] == "PRE_STABLE"
    assert any("PRE_BARN" in ex for ex in captured_calls[0]["existing_scene_hint"]["exits"])
    script_vars = (state.entity_states or {}).get("__script_vars__", {})
    assert script_vars.get("premapped_done") == "PRE_STABLE"

    stable_exits = (
        (
            await db_session.execute(
                select(WorldExit).where(
                    WorldExit.session_id == state.session_id,
                    WorldExit.from_scene_id == "PRE_STABLE",
                )
            )
        )
        .scalars()
        .all()
    )
    assert [e.to_scene_id for e in stable_exits] == ["PRE_BARN"]

    stable_entities = (
        (
            await db_session.execute(
                select(WorldEntity).where(
                    WorldEntity.session_id == state.session_id,
                    WorldEntity.current_scene_id == "PRE_STABLE",
                )
            )
        )
        .scalars()
        .all()
    )
    stable_ids = {ent.id for ent in stable_entities}
    assert "STATIC_PLAQUE" in stable_ids
    assert "PRE_STABLE_STABLE_HAND" in stable_ids
    assert "PRE_STABLE_OIL_LAMP" in stable_ids

    meta_mid = await AdventureLogic.get_all_scene_metadata(
        db_session, adv.id, session_id=state.session_id
    )
    assert "is_unknown" not in meta_mid["PRE_STABLE"]
    assert meta_mid["PRE_BARN"]["is_unknown"] is True

    # Act 2: Enter PRE_BARN (same zone_id) -> sees PRE_STABLE in cluster_context
    mat_barn = await materialize_dynamic_scene_for_exit(
        db=db_session,
        state=state,
        adventure=adv,
        user=user,
        world_exit=authored_link,
        origin_scene=mat_stable,
    )
    await db_session.commit()

    assert mat_barn.id == "PRE_BARN"
    assert mat_barn.dynamic_zone["materialized"] is True
    barn_cluster = captured_calls[1]["cluster_context"]
    assert isinstance(barn_cluster, list)
    assert any(c["scene_id"] == "PRE_STABLE" for c in barn_cluster)


@pytest.mark.asyncio
async def test_dynamic_generation_template_response_and_patch_roundtrip(db_session) -> None:
    """AdventureTemplateResponse and PATCH/GET endpoints preserve custom dynamic_generation settings."""
    from backend.api.routes.adventures.schemas import (
        AdventureTemplateResponse,
        AdventureTemplateUpdate,
    )
    from backend.api.routes.adventures.templates import get_adventure, update_adventure

    # Arrange
    user = User(
        id=str(uuid.uuid4()),
        username=f"dyn_cfg_{uuid.uuid4().hex[:8]}",
        hashed_password="x",
    )
    adv = AdventureTemplate(
        id=str(uuid.uuid4()),
        owner_id=user.id,
        title="Dynamic Config Test",
        is_ready=True,
        original_manifest={
            "title": "Dynamic Config Test",
            "adventure": {"title": "Dynamic Config Test"},
        },
    )
    db_session.add_all([user, adv])
    await db_session.commit()

    custom_cfg = {
        "scene_image_mode": "hq",
        "npc_image_mode": "off",
        "item_image_mode": "hq",
        "audio_mode": "generate",
        "generation_model": "world_builder",
        "max_npcs": 4,
        "npc_type_caps": {"humanoid": 1, "being": 3, "animal": 0, "monster": 4},
        "spawn_chances": {
            "npc": 80,
            "enemy": 65,
            "humanoid": 20,
            "being": 40,
            "animal": 0,
            "monster": 90,
            "item": 50,
            "container": 10,
            "switch": 5,
        },
        "interlude_quote_enabled": False,
    }

    # Act
    patched = await update_adventure(
        adv.id,
        AdventureTemplateUpdate(dynamic_generation=custom_cfg),
        db=db_session,
        current_user=user,
    )
    fetched = await get_adventure(adv.id, db=db_session, current_user=user)
    validated = AdventureTemplateResponse.model_validate(adv).model_dump()

    # Assert
    for data in (patched, fetched, validated):
        assert data["dynamic_generation"] == custom_cfg


@pytest.mark.asyncio
async def test_dynamic_zone_update_enable_disable_and_exit_scripts(db_session) -> None:
    """Scene/exit dynamic_zone can be saved and cleared cleanly, and create_editor_exit saves scripts."""
    from backend.api.routes.adventures.editing.entity_update.scene_exit import (
        _update_exit_dynamic_zone,
        _update_scene_dynamic_zone,
        update_exit,
    )
    from backend.api.routes.adventures.editing.schemas import (
        EntityUpdateRequest,
        ExitCreateRequest,
    )
    from backend.api.routes.adventures.editing.world_crud import create_editor_exit

    # Arrange
    user = User(
        id=str(uuid.uuid4()),
        username=f"dyn_zone_{uuid.uuid4().hex[:8]}",
        hashed_password="x",
    )
    adv = AdventureTemplate(
        id=str(uuid.uuid4()),
        owner_id=user.id,
        title="Exit Zone Test",
        is_ready=True,
        original_manifest={
            "exits": [
                {
                    "from_scene_id": "TOWN_GATE",
                    "to_scene_id": "STATIC_ROOM",
                    "label": "Old Gate",
                    "exit_type": "one_way",
                }
            ]
        },
    )
    gate = WorldScene(
        id="TOWN_GATE",
        template_id=adv.id,
        session_id=None,
        label="Town Gate",
        description="Stone gate.",
    )
    static_room = WorldScene(
        id="STATIC_ROOM",
        template_id=adv.id,
        session_id=None,
        label="Static Room",
        description="Static room.",
    )
    exit_row = WorldExit(
        id="EXIT_GATE",
        template_id=adv.id,
        session_id=None,
        from_scene_id="TOWN_GATE",
        to_scene_id="STATIC_ROOM",
        label="Old Gate",
        exit_type="one_way",
    )
    db_session.add_all([user, adv, gate, static_room, exit_row])
    await db_session.commit()

    zone_cfg = {
        "zone_id": "ZONE_CRYPTS",
        "theme": "Flooded ancient crypt",
        "depth": 1,
        "max_depth": 4,
        "danger_level": "high",
    }

    # Act 1: Enable and then explicitly disable dynamic_zone on scene and exit
    _update_scene_dynamic_zone(
        static_room,
        EntityUpdateRequest(target_type="scene", target_id=static_room.id, dynamic_zone=zone_cfg),
    )
    assert static_room.dynamic_zone is not None
    assert static_room.dynamic_zone["zone_id"] == "zone_crypts"

    _update_scene_dynamic_zone(
        static_room,
        EntityUpdateRequest(target_type="scene", target_id=static_room.id, dynamic_zone=None),
    )
    assert static_room.dynamic_zone is None

    await update_exit(
        db_session,
        adv.id,
        adv,
        EntityUpdateRequest(target_type="exit", target_id=exit_row.id, dynamic_zone=zone_cfg),
    )
    assert exit_row.dynamic_zone is not None
    assert exit_row.to_scene_id.startswith("DYN_")
    assert adv.original_manifest["exits"][0]["dynamic_zone"]["zone_id"] == "zone_crypts"

    _update_exit_dynamic_zone(
        exit_row,
        EntityUpdateRequest(target_type="exit", target_id=exit_row.id, dynamic_zone=None),
    )
    assert exit_row.dynamic_zone is None

    # Act 2: create_editor_exit persists script fields and unlock_expression
    created = await create_editor_exit(
        adv.id,
        ExitCreateRequest(
            from_scene_id="TOWN_GATE",
            to_scene_id="STATIC_ROOM",
            label="Rune Gate",
            lock_description="Sealed by a glyph.",
            unlock_expression="tw.vars.get('rune_key') == True",
            on_exit_used_script="tw.vars['entered_crypt'] = True",
            on_exit_used_text="The rune flares.",
            dynamic_zone=zone_cfg,
        ),
        db=db_session,
        current_user=user,
    )

    # Assert
    assert created["status"] == "success"
    assert created["exit"]["is_locked"] is True
    assert created["exit"]["unlock_expression"] == "tw.vars.get('rune_key') == True"
    assert created["exit"]["on_exit_used_script"] == "tw.vars['entered_crypt'] = True"
    assert created["exit"]["on_exit_used_text"] == "The rune flares."
    assert created["exit"]["dynamic_zone"]["zone_id"] == "zone_crypts"


@pytest.mark.asyncio
async def test_generate_dynamic_visuals_batches_five_objects_and_zone_key(monkeypatch) -> None:
    """generate_dynamic_visuals batches scene, NPCs, up to 5 objects, and fallback Zone Key in parallel."""
    import asyncio

    from backend.api.routes.adventures import dynamic_scene_media

    # Arrange
    in_flight = 0
    max_concurrent = 0
    calls: list[tuple[str, str]] = []

    async def _fake_generate_tier_image(**kwargs):
        nonlocal in_flight, max_concurrent
        in_flight += 1
        max_concurrent = max(max_concurrent, in_flight)
        calls.append((kwargs["prefix"], kwargs["tier"]))
        await asyncio.sleep(0)
        in_flight -= 1
        return f"/data/adventures/sessions/s1/dynamic_assets/{kwargs['prefix']}.webp"

    monkeypatch.setattr(dynamic_scene_media, "_generate_tier_image", _fake_generate_tier_image)

    payload = DynamicGeneratedScenePayload(
        name="Sunken Forge",
        description="A flooded dwarven smithy.",
        npcs=[
            DynamicGeneratedNpc(
                id="FORGE_GUARD",
                name="Rust Sentinel",
                description="An iron construct.",
            )
        ],
        objects=[
            DynamicGeneratedObject(
                id=f"OBJ_{idx}",
                name=f"Relic {idx}",
                description=f"Anvil relic {idx}.",
            )
            for idx in range(6)
        ],
    )

    # Act
    scene_img, npc_imgs, obj_imgs = await dynamic_scene_media.generate_dynamic_visuals(
        payload=payload,
        dyn_cfg={"scene_image_mode": "simple", "npc_image_mode": "simple", "item_image_mode": "hq"},
        origin_scene=None,
        user=object(),
        adventure=AdventureTemplate(id="adv1", owner_id="u1", title="Forge"),
        session_id="s1",
        target_id="DYN_FORGE_D1_1",
        zone_key_prompt_args=("Zone Key", "An iron passkey.", "ornate dwarven key"),
    )

    # Assert
    assert scene_img == "/data/adventures/sessions/s1/dynamic_assets/dyn_scene_dyn_forge_d1_1.webp"
    assert npc_imgs == {
        0: "/data/adventures/sessions/s1/dynamic_assets/dyn_npc_dyn_forge_d1_1_0.webp"
    }
    assert set(obj_imgs) == {0, 1, 2, 3, 4, -1}
    assert 5 not in obj_imgs
    assert (
        obj_imgs[-1] == "/data/adventures/sessions/s1/dynamic_assets/dyn_forge_d1_1_zone_key.webp"
    )
    assert max_concurrent == 8
    assert ("dyn_obj_dyn_forge_d1_1_5", "hq") not in calls


@pytest.mark.asyncio
async def test_materialize_dynamic_scene_defers_visuals_and_drains_into_db_and_map(
    db_session, monkeypatch
) -> None:
    """Deferred dynamic visuals persist scene/entities immediately and populate DB + map once drained."""
    import asyncio

    from backend.api.routes.adventures import dynamic_scene_media
    from backend.models.world_map import WorldMap

    # Arrange
    user, adv, state, origin_scene, dyn_exit = await _seed_dynamic_session(
        db_session, audio_mode="inherit"
    )
    adv.dynamic_generation = {
        "scene_image_mode": "simple",
        "npc_image_mode": "simple",
        "item_image_mode": "hq",
        "audio_mode": "inherit",
        "interlude_quote_enabled": False,
    }
    world_map = WorldMap(
        session_id=state.session_id,
        template_id=adv.id,
        nodes={
            "TOWN_GATE": {"label": "Town Gate", "image_url": None},
            "DYN_IRON_MINES_D1_1": {"label": "Flooded Gallery", "image_url": None},
        },
        edges=[],
        current_scene_id="TOWN_GATE",
    )
    db_session.add(world_map)
    await db_session.commit()

    release_visuals = asyncio.Event()

    async def _fake_generate_tier_image(**kwargs):
        await release_visuals.wait()
        return (
            f"/data/adventures/sessions/{state.session_id}/dynamic_assets/{kwargs['prefix']}.webp"
        )

    async def _fake_blueprint(**kwargs):
        return None

    async def _fake_scene_payload(**kwargs):
        return DynamicGeneratedScenePayload(
            name="Flooded Gallery",
            description="Dark water laps against rotted beams.",
            visual_description="Flooded timber mine gallery",
            npcs=[
                DynamicGeneratedNpc(
                    id="TUNNEL_BRUTE",
                    name="Cave Brute",
                    role="Guard",
                    description="Blocks the passage.",
                    attitude="hostile",
                    combat_role="standard",
                )
            ],
            objects=[
                DynamicGeneratedObject(
                    id="MINER_LAMP",
                    name="Oil Lamp",
                    item_type="STANDARD",
                    description="Brass mining lamp.",
                )
            ],
            forward_exits=[],
        )

    monkeypatch.setattr(dynamic_scene_media, "_generate_tier_image", _fake_generate_tier_image)
    monkeypatch.setattr(dynamic_scene_flow, "ensure_cluster_blueprint", _fake_blueprint)
    monkeypatch.setattr(dynamic_scene_flow, "generate_dynamic_scene_payload", _fake_scene_payload)

    pending: list[dynamic_scene_media.PendingDynamicVisuals] = []

    # Act 1: Materialize with pending_visuals -> persists rows right away while visuals are in flight
    scene = await materialize_dynamic_scene_for_exit(
        db=db_session,
        state=state,
        adventure=adv,
        user=user,
        world_exit=dyn_exit,
        origin_scene=origin_scene,
        pending_visuals=pending,
    )
    await db_session.commit()

    # Assert 1: Scene, entities, and fallback Zone Key exist immediately with image_url=None
    assert scene.image_url is None
    assert len(pending) == 1
    assert not pending[0].task.done()
    assert not await dynamic_scene_media.drain_pending_dynamic_visuals(
        db_session, state, pending, only_done=True
    )
    assert len(pending) == 1

    entities_before = (
        (
            await db_session.execute(
                select(WorldEntity).where(WorldEntity.session_id == state.session_id)
            )
        )
        .scalars()
        .all()
    )
    by_id_before = {ent.id: ent for ent in entities_before}
    assert "DYN_IRON_MINES_D1_1_TUNNEL_BRUTE" in by_id_before
    assert "DYN_IRON_MINES_D1_1_MINER_LAMP" in by_id_before
    assert "DYN_IRON_MINES_D1_1_ZONE_KEY" in by_id_before
    assert by_id_before["DYN_IRON_MINES_D1_1_ZONE_KEY"].image_url is None

    # Act 2: Release background tasks and drain them into DB + WorldMap
    release_visuals.set()
    applied = await dynamic_scene_media.drain_pending_dynamic_visuals(
        db_session, state, pending, only_done=False
    )
    await db_session.commit()

    # Assert 2: Scene, NPC, object, fallback Zone Key, and WorldMap node all receive generated URLs
    assert applied is True
    assert pending == []
    await db_session.refresh(scene)
    await db_session.refresh(world_map)
    entities_after = (
        (
            await db_session.execute(
                select(WorldEntity).where(WorldEntity.session_id == state.session_id)
            )
        )
        .scalars()
        .all()
    )
    by_id_after = {ent.id: ent for ent in entities_after}

    assert scene.image_url is not None
    assert scene.image_url.endswith("dyn_scene_dyn_iron_mines_d1_1.webp")
    assert world_map.nodes["DYN_IRON_MINES_D1_1"]["image_url"] == scene.image_url
    assert by_id_after["DYN_IRON_MINES_D1_1_TUNNEL_BRUTE"].image_url is not None
    assert by_id_after["DYN_IRON_MINES_D1_1_MINER_LAMP"].image_url is not None
    assert by_id_after["DYN_IRON_MINES_D1_1_ZONE_KEY"].image_url is not None
    assert by_id_after["DYN_IRON_MINES_D1_1_ZONE_KEY"].image_url.endswith(
        "dyn_iron_mines_d1_1_zone_key.webp"
    )


@pytest.mark.asyncio
async def test_start_dynamic_scene_audio_generation_triggers_immediately_during_materialization(
    db_session, monkeypatch
) -> None:
    """audio_mode='generate' launches start_missing_tracks immediately before visual generation completes."""
    from types import SimpleNamespace

    from backend.api.routes.adventures import dynamic_scene_media

    # Arrange
    user, adv, state, origin_scene, dyn_exit = await _seed_dynamic_session(
        db_session, audio_mode="generate"
    )
    adv.dynamic_generation = {
        "scene_image_mode": "simple",
        "npc_image_mode": "off",
        "item_image_mode": "off",
        "audio_mode": "generate",
        "interlude_quote_enabled": False,
    }
    await db_session.commit()

    started_audio_calls: list[tuple[str, list[str], str | None]] = []
    audio_seen_before_visuals: list[int] = []

    async def _fake_read_server_settings(_db):
        return SimpleNamespace(audio_settings={"enabled": True, "provider": "lyria"})

    def _fake_start_missing_tracks(session_id, tracks, raw, api_key):
        started_audio_calls.append((session_id, list(tracks.keys()), api_key))

    async def _fake_visuals(**kwargs):
        # Music rendering must already have been triggered before visuals run/finish
        audio_seen_before_visuals.append(len(started_audio_calls))
        return None, {}, {}

    async def _fake_blueprint(**kwargs):
        return None

    async def _fake_scene_payload(**kwargs):
        return DynamicGeneratedScenePayload(
            name="Resonant Vault",
            description="Crystal stalactites hum softly.",
            music_prompt="Eerie crystalline cavern drone",
            npcs=[],
            objects=[],
            forward_exits=[],
        )

    monkeypatch.setattr(dynamic_scene_media, "read_server_settings", _fake_read_server_settings)
    monkeypatch.setattr(dynamic_scene_media, "is_audio_available", lambda _raw: True)
    monkeypatch.setattr(dynamic_scene_media, "audio_api_key", lambda _u, _s: "sk-audio")
    monkeypatch.setattr(dynamic_scene_media, "start_missing_tracks", _fake_start_missing_tracks)
    monkeypatch.setattr(dynamic_scene_media, "generate_dynamic_visuals", _fake_visuals)
    monkeypatch.setattr(dynamic_scene_flow, "ensure_cluster_blueprint", _fake_blueprint)
    monkeypatch.setattr(dynamic_scene_flow, "generate_dynamic_scene_payload", _fake_scene_payload)

    # Act
    await materialize_dynamic_scene_for_exit(
        db=db_session,
        state=state,
        adventure=adv,
        user=user,
        world_exit=dyn_exit,
        origin_scene=origin_scene,
    )
    await db_session.commit()

    # Assert
    assert audio_seen_before_visuals == [1]
    assert len(started_audio_calls) == 1
    assert started_audio_calls[0][0] == state.session_id
    assert len(started_audio_calls[0][1]) == 1
    assert started_audio_calls[0][2] == "sk-audio"
    audio = read_audio_state(state.entity_states)
    assert started_audio_calls[0][1][0] in audio["tracks"]


def test_turn_llm_context_accepts_resolved_generator_model_settings() -> None:
    """TurnLlmContext accepts all kwargs returned by resolve_model_settings, including generator_model."""
    from backend.api.routes.adventures.turn_context_helpers import resolve_model_settings
    from backend.api.routes.adventures.turn_llm_pipeline import TurnLlmContext

    # Arrange
    resolved = resolve_model_settings(
        {
            "small_model_provider": "openrouter",
            "small_model": "deepseek/deepseek-flash",
            "complex_model_provider": "openai",
            "complex_model": "gpt-4o",
            "generator_model_provider": "ollama",
            "generator_model": "qwen3-coder",
        }
    )

    # Act
    ctx = TurnLlmContext(
        history=[],
        entities=[],
        all_entities=[],
        exits=[],
        all_scenes=[],
        global_unlock_rules_prompt_block="",
        mechanics_static_prompt="",
        narration_static_prompt="",
        mechanics_state_block="",
        narration_state_block="",
        mechanics_awards=[],
        **resolved,
    )

    # Assert
    assert ctx.generator_model_provider == "ollama"
    assert ctx.generator_model == "qwen3-coder"
    assert ctx.small_model_provider == "openrouter"


def test_tw_inventory_proxy_and_switch_guard() -> None:
    """tw.inventory and tw.player.has evaluate inventory checks and mutations inside sandbox/switch guards."""
    from backend.engine.interaction.switch_service import SwitchService
    from backend.engine.scripting.context import GameContext
    from backend.engine.scripting.sandbox import SafeAstInterpreter

    # Arrange
    expr = (
        "tw.inventory.has('TEST_PROBE') or tw.inventory.has('SECRET_ROOM_KEY') "
        "or tw.inventory.has('RESEARCH_TOKEN')"
    )
    empty_ctx = GameContext(avatar_data={"inventory": []})
    key_ctx = GameContext(
        avatar_data={"inventory": [{"id": "SECRET_ROOM_KEY", "name": "Secret Key"}]}
    )

    # Act & Assert: switch guard evaluation + sandbox membership/aliases
    ok_empty, reason_empty = SwitchService.evaluate_gate_expression(expr, empty_ctx)
    assert ok_empty is False
    assert reason_empty is not None

    ok_key, reason_key = SwitchService.evaluate_gate_expression(expr, key_ctx)
    assert ok_key is True
    assert reason_key is None
    assert key_ctx.player.has("secret_room_key") is True

    interp = SafeAstInterpreter()
    assert interp.evaluate_expression("'SECRET_ROOM_KEY' in tw.inventory", {"tw": key_ctx}) is True
    assert key_ctx.inventory.count() == 1
    assert len(key_ctx.inventory) == 1

    script_scope = {"tw": empty_ctx}
    interp.execute(
        "tw.inventory.add('RESEARCH_TOKEN', 'Research Token')\n"
        "has_before = tw.inventory.has('RESEARCH_TOKEN')\n"
        "tw.inventory.remove('RESEARCH_TOKEN')\n"
        "has_after = tw.inventory.has('RESEARCH_TOKEN')\n",
        script_scope,
    )
    assert script_scope["has_before"] is True
    assert script_scope["has_after"] is False
    assert empty_ctx.player.has("RESEARCH_TOKEN") is False
