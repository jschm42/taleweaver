"""Tests for dynamic scene challenges: NPC cloning, enemy keys/loot, climax bosses, and scripts."""

from __future__ import annotations

import pytest

from backend.api.routes.adventures.dynamic_challenge_helper import (
    apply_cluster_key_and_climax_progression,
    apply_dynamic_scripts_and_locks,
    build_dynamic_npc_clones,
    link_dynamic_npc_inventories,
    sanitize_dynamic_script,
    scale_enemy_hp,
)
from backend.api.routes.adventures.dynamic_scene_materialize import _build_object_entity
from backend.core.database import AsyncSessionLocal, engine
from backend.engine.world.dynamic_scene_generator import _roll_scene_plan
from backend.engine.world.dynamic_scene_schemas import (
    DynamicGeneratedNpc,
    DynamicGeneratedObject,
)
from backend.models.base import Base
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldEntity


def test_build_dynamic_npc_clones_hostile_and_neutral():
    state = SessionState(session_id="sess_1", current_scene_id="S1", entity_states={})
    goblin = DynamicGeneratedNpc(
        id="GOBLIN",
        name="Cave Goblin",
        npc_type="HUMANOID",
        attitude="hostile",
        combat_role="minion",
        clone_count=3,
        description="A snarling cave goblin.",
    )
    clones = build_dynamic_npc_clones(
        session_id="sess_1",
        target_id="DYN_DUNGEON_1",
        npc=goblin,
        image_url=None,
        state=state,
    )
    assert len(clones) == 3
    assert [ent.name for ent, _ in clones] == [
        "Cave Goblin #1",
        "Cave Goblin #2",
        "Cave Goblin #3",
    ]
    assert [primary for _, primary in clones] == [True, False, False]
    assert all(ent.id in state.entity_states for ent, _ in clones)

    villager = DynamicGeneratedNpc(
        id="VILLAGER",
        name="Villager",
        npc_type="HUMANOID",
        attitude="neutral",
        clone_count=4,
        description="A calm villager.",
    )
    neutral_clones = build_dynamic_npc_clones(
        session_id="sess_1",
        target_id="DYN_DUNGEON_1",
        npc=villager,
        image_url=None,
        state=state,
    )
    assert len(neutral_clones) == 1


def test_sanitize_dynamic_script_rewrites_ids_and_rejects_unsafe():
    chest = WorldEntity(
        id="DYN_1_CHEST",
        session_id="sess_1",
        entity_type="OBJECT",
        name="Oak Chest",
        current_scene_id="DYN_1",
    )
    raw_map = {"CHEST": chest}

    valid = sanitize_dynamic_script("tw.objects.unlock('CHEST')", raw_map)
    assert valid == "tw.objects.unlock('DYN_1_CHEST')"

    invalid = sanitize_dynamic_script("import os\nos.system('ls')", raw_map)
    assert invalid is None


def test_roll_scene_plan_climax_guarantees_hostile_and_container():
    plan = _roll_scene_plan(
        zone={
            "zone_id": "DUNGEON",
            "theme": "Stone dungeon",
            "depth": 3,
            "max_depth": 3,
            "cul_de_sac_on_max_depth": True,
            "spawn_chances": {"npc": 0, "enemy": 0, "container": 0, "item": 0},
        },
        max_npcs=2,
        effective_danger="medium",
    )
    assert plan["is_climax"] is True
    assert any(slot["attitude"] == "hostile" for slot in plan["npc_slots"])
    assert plan["allow_container"] is True
    assert "CONTAINER" in plan["allowed_item_types"]


@pytest.mark.asyncio
async def test_cluster_key_and_climax_boss_and_locked_chest():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        state = SessionState(session_id="sess_prog", current_scene_id="DYN_1", entity_states={})

        # Depth 1: hostile goblin drops/carries a zone key
        goblin_spec = DynamicGeneratedNpc(
            id="GOBLIN",
            name="Goblin",
            attitude="hostile",
            combat_role="minion",
            description="A goblin guard.",
        )
        clones = build_dynamic_npc_clones(
            session_id="sess_prog",
            target_id="DYN_1",
            npc=goblin_spec,
            image_url=None,
            state=state,
        )
        goblin_ent = clones[0][0]
        db.add(goblin_ent)

        await apply_cluster_key_and_climax_progression(
            db=db,
            state=state,
            zone={"zone_id": "DUNGEON", "depth": 1, "max_depth": 3, "danger_level": "medium"},
            target_id="DYN_1",
            npc_entities=[goblin_ent],
            object_entities=[],
        )
        await db.flush()
        assert len(goblin_ent.inventory) == 1
        key_id = goblin_ent.inventory[0]

        # Depth 3 (climax): boss promotion + locked reward container
        warden_spec = DynamicGeneratedNpc(
            id="WARDEN",
            name="Dungeon Warden",
            attitude="hostile",
            combat_role="standard",
            description="An armored warden.",
        )
        warden_ent = build_dynamic_npc_clones(
            session_id="sess_prog",
            target_id="DYN_3",
            npc=warden_spec,
            image_url=None,
            state=state,
        )[0][0]
        chest_spec = DynamicGeneratedObject(
            id="REWARD_CHEST",
            name="Boss Chest",
            item_type="CONTAINER",
            description="A heavy iron-bound chest.",
            on_interact_script="tw.story.narrate('You inspect the chest.')",
        )
        chest_ent = _build_object_entity(
            session_id="sess_prog",
            target_id="DYN_3",
            obj=chest_spec,
        )
        db.add_all([warden_ent, chest_ent])
        raw_map = {"REWARD_CHEST": chest_ent}
        link_dynamic_npc_inventories([(warden_spec, warden_ent, True)], raw_map)
        apply_dynamic_scripts_and_locks([chest_spec], [(warden_spec, warden_ent, True)], raw_map)

        await apply_cluster_key_and_climax_progression(
            db=db,
            state=state,
            zone={
                "zone_id": "DUNGEON",
                "depth": 3,
                "max_depth": 3,
                "cul_de_sac_on_max_depth": True,
                "danger_level": "high",
            },
            target_id="DYN_3",
            npc_entities=[warden_ent],
            object_entities=[chest_ent],
        )
        assert warden_ent.metadata_json["combat_role"] == "boss"
        assert warden_ent.hp == scale_enemy_hp("boss", 100, danger="high")
        assert chest_ent.metadata_json["locked"] is True
        assert chest_ent.metadata_json["item_to_unlock"] == key_id
        assert (
            chest_ent.metadata_json["on_interact_script"]
            == "tw.story.narrate('You inspect the chest.')"
        )
        await db.rollback()


def test_dynamic_attack_on_sight_and_recruitable_companion():
    from backend.engine.scripting.sandbox import SafeAstInterpreter

    state = SessionState(session_id="sess_2", current_scene_id="S1", entity_states={})
    ambusher = DynamicGeneratedNpc(
        id="STALKER",
        name="Shadow Stalker",
        npc_type="MONSTER",
        attitude="hostile",
        combat_role="standard",
        attack_mode="ATTACK_ON_SIGHT",
        description="Leaps from the shadows.",
    )
    stalker_ent = build_dynamic_npc_clones(
        session_id="sess_2",
        target_id="DYN_2",
        npc=ambusher,
        image_url=None,
        state=state,
    )[0][0]
    assert stalker_ent.metadata_json["attack_mode"] == "ATTACK_ON_SIGHT"

    stray_hound = DynamicGeneratedNpc(
        id="HOUND",
        name="Scruffy Hound",
        npc_type="ANIMAL",
        attitude="friendly",
        is_recruitable_companion=True,
        companion_tactics="OFFENSIVE",
        companion_banter="QUIET",
        description="A loyal stray hound.",
    )
    hound_ent = build_dynamic_npc_clones(
        session_id="sess_2",
        target_id="DYN_2",
        npc=stray_hound,
        image_url=None,
        state=state,
    )[0][0]
    comp = hound_ent.metadata_json.get("companion")
    assert comp == {
        "recruitable": True,
        "starts_in_party": False,
        "tactics": "OFFENSIVE",
        "banter": "QUIET",
        "downed_recovery": 0.25,
        "recruit_mode": "INSTANT",
    }
    assert hound_ent.metadata_json["main_attack"]["damage_dice"] == "1d6"
    assert "joins your party" in hound_ent.metadata_json["on_recruit_success_text"]
    script = hound_ent.metadata_json["on_interact_script"]
    assert "tw.party.dismiss(" in script
    assert SafeAstInterpreter.check_syntax(script) == []


def test_party_hp_scaling_for_elites_bosses_and_packs():
    # Solo 100 HP protagonist: elite is 55 HP, boss is 85 HP (not 140-220 HP)
    assert scale_enemy_hp("elite", 100, danger="medium") == 55
    assert scale_enemy_hp("boss", 100, danger="medium") == 85

    # With a 30 HP companion (130 HP party): boss scales to 110 HP
    assert scale_enemy_hp("boss", 130, danger="medium") == 110

    # Pack of 3 minions scales down per-clone HP
    single_minion = scale_enemy_hp("minion", 100, danger="medium", clone_count=1)
    pack_minion = scale_enemy_hp("minion", 100, danger="medium", clone_count=3)
    assert pack_minion < single_minion
    assert pack_minion >= 12


@pytest.mark.asyncio
async def test_llm_zone_key_flag_and_custom_tone_resolution():
    from types import SimpleNamespace

    from backend.api.routes.adventures.dynamic_challenge_helper import (
        _build_fallback_key_appearance,
        _is_key_item,
    )
    from backend.api.routes.adventures.dynamic_scene_media import extract_tone_text

    # Custom admin tone from user.tone_catalog + selected_tone dict resolves full stylistic guidance
    user = SimpleNamespace(
        tone_catalog=[
            {
                "id": "neon_noir",
                "name": "Neon Noir",
                "instruction": "Gritty cyber-industrial sci-fi atmosphere with rain and holograms.",
            }
        ]
    )
    adv = SimpleNamespace(
        selected_tone={"id": "neon_noir", "name": "Neon Noir"},
        cover_appearance="rain-slicked orbital station corridor",
    )
    resolved_tone = extract_tone_text(adv, user)
    assert "Neon Noir" in resolved_tone
    assert "cyber-industrial sci-fi" in resolved_tone

    appearance = _build_fallback_key_appearance({"theme": "Derelict reactor deck"}, adv, user)
    assert "Neon Noir" in appearance
    assert "Derelict reactor deck" in appearance
    assert "rain-slicked orbital station corridor" in appearance

    # LLM-generated object with is_zone_key=True does not need "key" in its name to unlock climax chest
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        state = SessionState(session_id="sess_zone_flag", current_scene_id="S1", entity_states={})
        guard_spec = DynamicGeneratedNpc(
            id="DRONE",
            name="Security Drone",
            attitude="hostile",
            combat_role="standard",
            inventory=["ACCESS_CHIP"],
            description="Patrolling automaton.",
        )
        chip_spec = DynamicGeneratedObject(
            id="ACCESS_CHIP",
            name="Biometric Access Chip",
            description="Encoded override token.",
            is_zone_key=True,
        )
        guard_ent = build_dynamic_npc_clones(
            session_id="sess_zone_flag",
            target_id="S1",
            npc=guard_spec,
            image_url=None,
            state=state,
        )[0][0]
        chip_ent = _build_object_entity(session_id="sess_zone_flag", target_id="S1", obj=chip_spec)
        assert chip_ent.metadata_json.get("is_zone_key") is True
        assert _is_key_item(chip_ent) is True

        link_dynamic_npc_inventories([(guard_spec, guard_ent, True)], {"ACCESS_CHIP": chip_ent})
        db.add_all([guard_ent, chip_ent])

        await apply_cluster_key_and_climax_progression(
            db=db,
            state=state,
            zone={"zone_id": "SECTOR_7", "depth": 1, "max_depth": 3, "danger_level": "medium"},
            target_id="S1",
            npc_entities=[guard_ent],
            object_entities=[chip_ent],
            user=user,
            adventure=adv,
        )
        # Existing LLM key tagged rather than spawning a fallback key
        assert guard_ent.inventory == [chip_ent.id]
        assert chip_ent.metadata_json.get("dynamic_zone_key_for") == "SECTOR_7"

        locker_ent = _build_object_entity(
            session_id="sess_zone_flag",
            target_id="S3",
            obj=DynamicGeneratedObject(
                id="ARMORY_LOCKER",
                name="Sealed Locker",
                item_type="CONTAINER",
                description="Heavy bulkhead locker.",
            ),
        )
        boss_ent = build_dynamic_npc_clones(
            session_id="sess_zone_flag",
            target_id="S3",
            npc=DynamicGeneratedNpc(
                id="SENTINEL",
                name="Reactor Sentinel",
                attitude="hostile",
                combat_role="standard",
                description="Heavy mech unit.",
            ),
            image_url=None,
            state=state,
        )[0][0]
        db.add_all([locker_ent, boss_ent])

        await apply_cluster_key_and_climax_progression(
            db=db,
            state=state,
            zone={
                "zone_id": "SECTOR_7",
                "depth": 3,
                "max_depth": 3,
                "cul_de_sac_on_max_depth": True,
                "danger_level": "medium",
            },
            target_id="S3",
            npc_entities=[boss_ent],
            object_entities=[locker_ent],
            user=user,
            adventure=adv,
        )
        assert locker_ent.metadata_json["locked"] is True
        assert locker_ent.metadata_json["item_to_unlock"] == chip_ent.id
        await db.rollback()


def test_dynamic_weapons_and_potions_scale_with_party_and_enemy_hp():
    from backend.api.routes.adventures.agent_combat_math import average_amount
    from backend.api.routes.adventures.combat.combatants import DICE_RX
    from backend.api.routes.adventures.dynamic_challenge_helper import (
        average_dice_value,
        scale_dynamic_object_stats,
    )
    from backend.engine.rules.skill_check import roll_dice_detailed

    # Shorthand Nd+K dice notation is parsed as implicit d6 across engine and math helpers
    assert DICE_RX.match("1d+2")
    assert average_amount("1d+2") == 5.5
    rolled = roll_dice_detailed("1d+2")
    assert 3 <= rolled["total"] <= 8

    # 1. Weak weapon and potion scale up to match medium-danger party_hp=100 & enemy_hps=[35]
    weak_sword = DynamicGeneratedObject(
        id="RUSTY_BLADE",
        name="Rusty Blade",
        item_type="WEAPON",
        damage_dice="1d4",
        description="Dull shortblade.",
    )
    weak_potion = DynamicGeneratedObject(
        id="WEAK_VIAL",
        name="Diluted Salve",
        item_type="CONSUMABLE",
        hp_change=3,
        description="A tiny sip of herbs.",
    )
    scale_dynamic_object_stats(weak_sword, party_hp=100, enemy_hps=[35], danger="medium")
    scale_dynamic_object_stats(weak_potion, party_hp=100, enemy_hps=[35], danger="medium")
    assert 7.0 <= average_dice_value(weak_sword.damage_dice) <= 12.0
    assert weak_potion.hp_change >= 16

    # Shorthand '1d+2' at party_hp=100 / enemy_hps=[35] stays valid without clamping
    shorthand_blade = DynamicGeneratedObject(
        id="IRON_EDGE",
        name="Iron Edge",
        item_type="WEAPON",
        damage_dice="1d+2",
        description="Balanced iron blade.",
    )
    scale_dynamic_object_stats(shorthand_blade, party_hp=100, enemy_hps=[35], danger="medium")
    assert shorthand_blade.damage_dice == "1d+2"

    # 2. Overpowered weapon & potion clamp down for low-HP party_hp=50 & enemy_hps=[14]
    god_axe = DynamicGeneratedObject(
        id="GOD_AXE",
        name="Worldbreaker Axe",
        item_type="WEAPON",
        damage_dice="8d10+20",
        description="Far too strong for early scenes.",
    )
    mega_potion = DynamicGeneratedObject(
        id="MEGA_POTION",
        name="Elixir of Immortality",
        item_type="CONSUMABLE",
        hp_change=100,
        description="Too potent for early scenes.",
    )
    scale_dynamic_object_stats(god_axe, party_hp=50, enemy_hps=[14], danger="low")
    scale_dynamic_object_stats(mega_potion, party_hp=50, enemy_hps=[14], danger="low")
    assert average_dice_value(god_axe.damage_dice) <= 7.0
    assert mega_potion.hp_change <= 25

    # 3. High-HP climax scaling boosts weapons, potions, and wearable caps proportionally
    climax_spear = DynamicGeneratedObject(
        id="STAR_LANCE",
        name="Starlight Lance",
        item_type="WEAPON",
        damage_dice="1d6",
        description="Under-statted endgame spear.",
    )
    climax_tonic = DynamicGeneratedObject(
        id="PHOENIX_TONIC",
        name="Phoenix Tonic",
        item_type="CONSUMABLE",
        hp_change=15,
        description="Needs to heal enough for high-HP combat.",
    )
    scale_dynamic_object_stats(
        climax_spear, party_hp=200, enemy_hps=[95], danger="high", is_climax=True
    )
    scale_dynamic_object_stats(
        climax_tonic, party_hp=200, enemy_hps=[95], danger="high", is_climax=True
    )
    assert average_dice_value(climax_spear.damage_dice) > 18.0
    assert climax_tonic.hp_change >= 40

    # 4. Hostile NPCs built with build_dynamic_npc_clones receive a scaled main_attack
    state = SessionState(session_id="sess_attack_scale", current_scene_id="S1", entity_states={})
    elite_spec = DynamicGeneratedNpc(
        id="WARLORD",
        name="Void Warlord",
        attitude="hostile",
        combat_role="elite",
        description="Armored commander.",
    )
    minion_spec = DynamicGeneratedNpc(
        id="IMP",
        name="Ash Imp",
        attitude="hostile",
        combat_role="minion",
        description="Fragile nuisance.",
    )
    elite_ent = build_dynamic_npc_clones(
        session_id="sess_attack_scale",
        target_id="S1",
        npc=elite_spec,
        image_url=None,
        state=state,
        party_hp=180,
        danger="high",
    )[0][0]
    minion_ent = build_dynamic_npc_clones(
        session_id="sess_attack_scale",
        target_id="S1",
        npc=minion_spec,
        image_url=None,
        state=state,
        party_hp=60,
        danger="low",
    )[0][0]
    elite_avg = average_dice_value(
        (elite_ent.metadata_json.get("main_attack") or {}).get("damage_dice")
    )
    minion_avg = average_dice_value(
        (minion_ent.metadata_json.get("main_attack") or {}).get("damage_dice")
    )
    assert elite_avg > minion_avg
    assert elite_avg >= 20.0


async def _seed_cluster_blueprint_session(db):
    import uuid

    from backend.models.adventure_template import AdventureTemplate
    from backend.models.avatar import Avatar
    from backend.models.game_session import GameSession
    from backend.models.user import User
    from backend.models.world_entity import WorldExit, WorldScene

    uid = str(uuid.uuid4())
    adv_id = str(uuid.uuid4())
    short = uuid.uuid4().hex[:6].upper()
    sess_id = f"sess_bp_{short.lower()}"
    origin_id = f"CHAPEL_{short}"
    entry_id = f"DYN_CAT_{short}"
    zone_id = f"sunless_catacombs_{short.lower()}"
    user = User(id=uid, username=f"bp_user_{short.lower()}", hashed_password="x")
    adv = AdventureTemplate(
        id=adv_id,
        owner_id=uid,
        title="Chapel of Ash",
        teaser="Beneath the sunken altar",
        plot="Uncover the relic sealed below the chapel.",
        is_ready=True,
        dynamic_generation={
            "scene_image_mode": "off",
            "npc_image_mode": "off",
            "item_image_mode": "off",
            "audio_mode": "empty",
            "interlude_quote_enabled": False,
        },
    )
    avatar = Avatar(id=str(uuid.uuid4()), user_id=uid, template_id=adv_id, name="Aric")
    game = GameSession(id=sess_id, template_id=adv_id, user_id=uid, avatar_id=avatar.id)
    origin_scene = WorldScene(
        id=origin_id,
        template_id=None,
        session_id=sess_id,
        label="Chapel Nave",
        description="Cracked flagstones lead toward a stone stair.",
    )
    state = SessionState(
        session_id=sess_id,
        template_id=adv_id,
        user_id=uid,
        avatar_id=avatar.id,
        current_scene_id=origin_id,
        entity_states={},
    )
    dyn_exit = WorldExit(
        id=f"EXIT_CAT_{short}",
        template_id=None,
        session_id=sess_id,
        from_scene_id=origin_id,
        to_scene_id=entry_id,
        label="Descend into the Catacombs",
        exit_type="one_way",
        dynamic_zone={
            "enabled": True,
            "zone_id": zone_id,
            "theme": "Flooded catacombs under the chapel",
            "depth": 1,
            "max_depth": 3,
            "danger_level": "medium",
            "max_npcs": 2,
            "cul_de_sac_on_max_depth": True,
        },
    )
    db.add_all([user, adv, avatar, game, origin_scene, state, dyn_exit])
    await db.commit()
    return user, adv, state, origin_scene, dyn_exit, sess_id, zone_id


def _assert_rooms_have_own_briefs(room_zones: list[dict]) -> None:
    assert len({z["theme"] for z in room_zones}) == len(room_zones)
    assert len({z["instructions"] for z in room_zones}) == len(room_zones)
    assert all(z["instructions_source"] == "cluster_blueprint" for z in room_zones)
    assert all(z["root_theme"] == "Flooded catacombs under the chapel" for z in room_zones)


@pytest.mark.asyncio
async def test_cluster_blueprint_diamond_graph_and_lazy_materialization():
    from sqlalchemy import select

    from backend.api.routes.adventures.dynamic_cluster_graph import (
        DYNAMIC_CLUSTER_BP_KEY,
        get_cluster_blueprint,
    )
    from backend.api.routes.adventures.dynamic_scene_flow import materialize_dynamic_scene_for_exit
    from backend.engine.world.dynamic_cluster_blueprint import (
        build_cluster_blueprint_prompt_section,
    )
    from backend.engine.world.dynamic_scene_generator import _build_scene_prompts
    from backend.models.world_entity import WorldExit, WorldScene

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        (
            user,
            adv,
            state,
            origin_scene,
            dyn_exit,
            sess_id,
            zone_id,
        ) = await _seed_cluster_blueprint_session(db)

        # 1. Enter depth 1 -> builds cluster blueprint & persists full 4-node Diamond graph
        scene_d1 = await materialize_dynamic_scene_for_exit(
            db=db,
            state=state,
            adventure=adv,
            user=user,
            world_exit=dyn_exit,
            origin_scene=origin_scene,
        )
        await db.commit()

        assert scene_d1.id == dyn_exit.to_scene_id
        assert DYNAMIC_CLUSTER_BP_KEY in (state.entity_states or {})
        cluster_bp = get_cluster_blueprint(state, zone_id)
        assert cluster_bp is not None
        assert cluster_bp["cluster_title"]
        assert cluster_bp["story_arc"]
        assert cluster_bp["climax_goal"]
        assert cluster_bp["key_item_concept"]

        nodes_by_id = {n["node_id"]: n for n in cluster_bp["nodes"]}
        assert list(nodes_by_id.keys()) == ["D1_1", "D2_1", "D2_2", "D3_1"]
        assert [nodes_by_id[k]["role"] for k in ("D1_1", "D2_1", "D2_2", "D3_1")] == [
            "entry",
            "obstacle",
            "branch",
            "climax",
        ]
        assert {(e["from_node_id"], e["to_node_id"]) for e in cluster_bp["edges"]} == {
            ("D1_1", "D2_1"),
            ("D1_1", "D2_2"),
            ("D2_1", "D3_1"),
            ("D2_2", "D3_1"),
        }

        # 2. All 4 WorldScenes and all 4 forward WorldExits exist in DB immediately
        scene_rows = {
            row.id: row
            for row in (
                await db.execute(select(WorldScene).where(WorldScene.session_id == sess_id))
            ).scalars()
        }
        d2_1_sid = nodes_by_id["D2_1"]["scene_id"]
        d2_2_sid = nodes_by_id["D2_2"]["scene_id"]
        d3_1_sid = nodes_by_id["D3_1"]["scene_id"]
        assert {scene_d1.id, d2_1_sid, d2_2_sid, d3_1_sid} <= set(scene_rows.keys())
        assert not any(
            scene_rows[sid].dynamic_zone["materialized"] for sid in (d2_1_sid, d2_2_sid, d3_1_sid)
        )
        assert scene_rows[d3_1_sid].dynamic_zone["cluster_node"]["role"] == "climax"

        # Every room carries its own sub-theme and generation instructions from the blueprint
        _assert_rooms_have_own_briefs(
            [scene_rows[sid].dynamic_zone for sid in (scene_d1.id, d2_1_sid, d2_2_sid, d3_1_sid)]
        )

        # 3. Blueprint prompt section injects story arc, climax goal, and climax depth rule
        bp_text = build_cluster_blueprint_prompt_section(scene_rows[d3_1_sid].dynamic_zone)
        assert cluster_bp["story_arc"] in bp_text
        assert cluster_bp["climax_goal"] in bp_text
        _sys_p, user_p = _build_scene_prompts(
            adventure_title=adv.title,
            adventure_setting=adv.plot,
            adventure_tone="Dark Fantasy",
            origin_scene_name=scene_d1.label,
            origin_scene_description=scene_d1.description,
            exit_label="To Sanctum",
            zone=scene_rows[d3_1_sid].dynamic_zone,
            language="English",
            effective_danger="medium",
            max_npcs=2,
            scene_plan={
                "target_npcs": 1,
                "npc_slots": [{"npc_type": "MONSTER", "attitude": "hostile"}],
                "target_objects": 2,
                "allowed_item_types": ["STANDARD", "CONTAINER"],
                "allow_container": True,
                "allow_switch": False,
            },
            existing_scene_hint={"id": d3_1_sid, "label": "Sanctum", "exits": []},
        )
        assert "CLIMAX DEPTH (3/3)" in user_p
        assert cluster_bp["story_arc"] in user_p

        exit_rows = {
            (row.from_scene_id, row.to_scene_id): row
            for row in (
                await db.execute(select(WorldExit).where(WorldExit.session_id == sess_id))
            ).scalars()
        }
        assert {
            (scene_d1.id, d2_1_sid),
            (scene_d1.id, d2_2_sid),
            (d2_1_sid, d3_1_sid),
            (d2_2_sid, d3_1_sid),
        } <= set(exit_rows.keys())

        # 4. Lazy in-place materialization along D1_1 -> D2_1 -> D3_1 & convergence from D2_2 -> D3_1
        mat_d2_1 = await materialize_dynamic_scene_for_exit(
            db=db,
            state=state,
            adventure=adv,
            user=user,
            world_exit=exit_rows[(scene_d1.id, d2_1_sid)],
            origin_scene=scene_d1,
        )
        mat_d3_1 = await materialize_dynamic_scene_for_exit(
            db=db,
            state=state,
            adventure=adv,
            user=user,
            world_exit=exit_rows[(d2_1_sid, d3_1_sid)],
            origin_scene=mat_d2_1,
        )
        mat_d2_2 = await materialize_dynamic_scene_for_exit(
            db=db,
            state=state,
            adventure=adv,
            user=user,
            world_exit=exit_rows[(scene_d1.id, d2_2_sid)],
            origin_scene=scene_d1,
        )
        mat_d3_from_branch = await materialize_dynamic_scene_for_exit(
            db=db,
            state=state,
            adventure=adv,
            user=user,
            world_exit=exit_rows[(d2_2_sid, d3_1_sid)],
            origin_scene=mat_d2_2,
        )
        assert mat_d2_1.id == d2_1_sid
        assert mat_d2_1.dynamic_zone["materialized"] is True
        assert mat_d3_1.id == d3_1_sid
        assert mat_d3_1.dynamic_zone["materialized"] is True
        assert mat_d3_from_branch.id == d3_1_sid
        await db.rollback()


@pytest.mark.asyncio
async def test_build_existing_scene_context_prompt_section_string_and_dict_hints():
    from sqlalchemy import select

    from backend.api.routes.adventures.dynamic_cluster_graph import get_cluster_blueprint
    from backend.api.routes.adventures.dynamic_scene_flow import materialize_dynamic_scene_for_exit
    from backend.api.routes.adventures.dynamic_scene_materialize import (
        _collect_existing_scene_hint,
    )
    from backend.engine.world.dynamic_instructions_helper import (
        build_existing_scene_context_prompt_section,
    )
    from backend.engine.world.dynamic_scene_generator import _build_scene_prompts
    from backend.models.world_entity import WorldScene

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        (
            user,
            adv,
            state,
            origin_scene,
            dyn_exit,
            sess_id,
            zone_id,
        ) = await _seed_cluster_blueprint_session(db)
        scene_d1 = await materialize_dynamic_scene_for_exit(
            db=db,
            state=state,
            adventure=adv,
            user=user,
            world_exit=dyn_exit,
            origin_scene=origin_scene,
        )
        cluster_bp = get_cluster_blueprint(state, zone_id)
        d2_1_sid = {n["node_id"]: n for n in cluster_bp["nodes"]}["D2_1"]["scene_id"]
        d2_1_scene = (
            await db.execute(select(WorldScene).where(WorldScene.id == d2_1_sid))
        ).scalar_one()
        d2_1_scene.description = "A flooded watchpost guarding the inner sanctum."
        db.add(
            WorldEntity(
                id=f"LANTERN_{zone_id}",
                template_id=None,
                session_id=sess_id,
                name="Signal Lantern",
                entity_type="OBJECT",
                description="A bronze lantern.",
                current_scene_id=d2_1_sid,
            )
        )
        await db.flush()

        d2_1_hint = await _collect_existing_scene_hint(db, sess_id, d2_1_scene)
        assert d2_1_hint["exits"]
        assert isinstance(d2_1_hint["exits"][0], str)
        assert d2_1_hint["entities"] == ["Signal Lantern (OBJECT)"]

        section = build_existing_scene_context_prompt_section(d2_1_hint)
        assert "A flooded watchpost guarding the inner sanctum." in section
        assert d2_1_hint["exits"][0] in section
        assert "Signal Lantern (OBJECT)" in section

        _sys_p, user_p = _build_scene_prompts(
            adventure_title=adv.title,
            adventure_setting=adv.plot,
            adventure_tone="Dark Fantasy",
            origin_scene_name=scene_d1.label,
            origin_scene_description=scene_d1.description,
            exit_label="Advance to D2_1",
            zone=d2_1_scene.dynamic_zone,
            language="English",
            effective_danger="medium",
            max_npcs=2,
            scene_plan=_roll_scene_plan(
                zone=d2_1_scene.dynamic_zone,
                max_npcs=2,
                effective_danger="medium",
            ),
            existing_scene_hint=d2_1_hint,
        )
        assert d2_1_hint["exits"][0] in user_p
        assert "Signal Lantern (OBJECT)" in user_p
        assert "A flooded watchpost guarding the inner sanctum." in user_p
        await db.rollback()

    dict_section = build_existing_scene_context_prompt_section(
        {
            "label": "Gatehouse",
            "premise": "Guarded crossing.",
            "exits": [{"label": "North Gate", "to_scene_id": "BARN", "is_locked": True}],
            "existing_npcs": [{"id": "WARDEN", "name": "Gate Warden"}],
            "existing_objects": [{"id": "CHEST", "name": "Iron Chest", "item_type": "CONTAINER"}],
        }
    )
    assert "'North Gate' -> BARN [locked]" in dict_section
    assert "WARDEN (Gate Warden)" in dict_section
    assert "CHEST (Iron Chest, CONTAINER)" in dict_section


@pytest.mark.asyncio
async def test_dynamic_generation_model_config_override_and_blueprint(monkeypatch):
    from types import SimpleNamespace

    from backend.engine.blueprint import analyze_blueprint, apply_blueprint
    from backend.engine.world import dynamic_cluster_architect as arch_mod
    from backend.engine.world import dynamic_cluster_blueprint as bp_mod
    from backend.engine.world import dynamic_scene_generator as gen_mod
    from backend.engine.world.dynamic_scene_schemas import (
        DynamicGeneratedScenePayload,
        normalize_dynamic_generation,
        normalize_dynamic_zone,
    )

    assert normalize_dynamic_generation({})["generation_model"] == "mechanics"
    assert normalize_dynamic_generation({"generation_model": "complex"})["generation_model"] == (
        "narration"
    )
    assert (
        normalize_dynamic_generation({"generation_model": "WorldBuilder"})["generation_model"]
        == "world_builder"
    )

    zone_default = normalize_dynamic_zone({"zone_id": "crypt", "theme": "Sunken crypt"})
    zone_narr = normalize_dynamic_zone(
        {"zone_id": "crypt", "theme": "Sunken crypt", "generation_model": "narration"}
    )
    zone_wb = normalize_dynamic_zone(
        {"zone_id": "crypt", "theme": "Sunken crypt", "generation_model": "generator"}
    )
    assert zone_default is not None and zone_default["generation_model"] is None
    assert zone_narr is not None and zone_narr["generation_model"] == "narration"
    assert zone_wb is not None and zone_wb["generation_model"] == "world_builder"

    fake_user = SimpleNamespace(
        llm_settings={
            "small_model_provider": "ollama",
            "small_model": "mech-model",
            "complex_model_provider": "ollama",
            "complex_model": "narr-model",
            "generator_model_provider": "ollama",
            "generator_model": "wb-model",
        },
        encrypted_api_keys={},
    )
    assert arch_mod.resolve_dynamic_llm_model(fake_user, zone_default, None) == (
        "ollama",
        "mech-model",
        "small",
    )
    assert arch_mod.resolve_dynamic_llm_model(
        fake_user, zone_default, {"generation_model": "narration"}
    ) == ("ollama", "narr-model", "complex")
    assert arch_mod.resolve_dynamic_llm_model(
        fake_user, zone_wb, {"generation_model": "narration"}
    ) == ("ollama", "wb-model", "generator")

    captured: list[tuple[str, str]] = []

    class _StubLLM:
        def __init__(self, _user, *, provider: str, model_category: str) -> None:
            self._category = model_category

        async def aexecute_complex_task(self, _sys, _usr, schema, model, **_kwargs):
            captured.append((self._category, model))
            if schema is bp_mod.DynamicClusterBlueprint:
                return bp_mod.build_fallback_cluster_blueprint("Tunnel", zone_wb)
            return DynamicGeneratedScenePayload(
                name="Obsidian Vault",
                description="Columns of volcanic glass frame a quiet chamber.",
            )

    monkeypatch.setattr(arch_mod, "GameMasterLLM", _StubLLM)
    monkeypatch.setattr(gen_mod, "GameMasterLLM", _StubLLM)

    await arch_mod.generate_dynamic_cluster_blueprint(
        adventure_title="Test",
        adventure_setting="Plot",
        adventure_tone="Dark",
        origin_scene_name="Hall",
        origin_scene_description="A stone hall.",
        exit_label="Iron Gate",
        zone=zone_wb,
        user=fake_user,
        generation_config={"generation_model": "mechanics"},
    )
    async with AsyncSessionLocal() as db:
        await gen_mod.generate_dynamic_scene_payload(
            adventure_title="Test",
            adventure_setting="Plot",
            adventure_tone="Dark",
            origin_scene_name="Hall",
            origin_scene_description="A stone hall.",
            exit_label="Iron Gate",
            dynamic_zone=zone_default,
            user=fake_user,
            db=db,
            generation_config={"generation_model": "narration"},
        )
    assert captured == [("generator", "wb-model"), ("complex", "narr-model")]

    source = """
    [World]
    dynamic_model: narration

    [Scene: GATE] Ruined Gate
    Cracked flagstones.

    [Exit: GATE -> ?] Sunken Stairway
    zone: sunken_crypt
    theme: Flooded subterranean crypt
    generation_model: world_builder
    """
    blueprint, _missing = analyze_blueprint(source)
    manifest: dict = {"scenes": [{"id": "GATE", "label": "Ruined Gate"}], "exits": []}
    violations = apply_blueprint(manifest, blueprint)
    assert blueprint.errors == []
    assert violations == []
    assert manifest["dynamic_generation"]["generation_model"] == "narration"
    assert manifest["exits"][0]["dynamic_zone"]["generation_model"] == "world_builder"
