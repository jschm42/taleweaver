"""Scoped LLM generators for procedural Dynamic Scenes and interlude quotes."""

from __future__ import annotations

import logging
import random
import re
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.turn_context_helpers import resolve_model_settings
from backend.core.api_keys import has_api_key
from backend.core.llm_router import GameMasterLLM
from backend.engine.world.dynamic_cluster_architect import resolve_dynamic_llm_model
from backend.engine.world.dynamic_cluster_blueprint import build_cluster_blueprint_prompt_section
from backend.engine.world.dynamic_instructions_helper import (
    adjust_plan_for_instructions,
    apply_instructions_backfill,
    build_cluster_consistency_prompt_section,
    build_existing_scene_context_prompt_section,
    build_instructions_prompt_section,
    ensure_object_item_stats,
    select_planned_objects,
)
from backend.engine.world.dynamic_interlude_quote import (
    _build_interlude_prompts,
    _pick_interlude_npc,
    _strip_outer_quotes,
)
from backend.engine.world.dynamic_required_entities import (
    cap_npcs,
    is_protected,
    merge_required_entities,
    raise_plan_for_required,
    required_blocks,
    required_prompt_section,
    split_protected,
)
from backend.engine.world.dynamic_scene_schemas import (
    DynamicGeneratedChildExit,
    DynamicGeneratedScenePayload,
    DynamicInterludeQuotePayload,
    normalize_dynamic_zone,
    resolve_effective_dynamic_rules,
)

logger = logging.getLogger(__name__)

_LOCAL_LLM_PROVIDERS = {"ollama", "lmstudio"}
_RANDOM_DANGER_CHOICES: tuple[str, ...] = ("peaceful", "low", "medium", "high", "deadly")


def _has_provider_credentials(user: Any, provider: str) -> bool:
    if provider in _LOCAL_LLM_PROVIDERS:
        return True
    keys = getattr(user, "encrypted_api_keys", None) or {}
    return has_api_key(keys, provider)


async def generate_dynamic_interlude_quote(
    *,
    adventure_title: str,
    adventure_setting: str,
    adventure_tone: str,
    origin_scene_name: str,
    exit_label: str,
    zone_theme: str,
    candidate_npcs: list[dict[str, Any]],
    user: Any,
    db: AsyncSession,
    adventure_id: Optional[str] = None,
    game_id: Optional[str] = None,
    language: str = "English",
) -> Optional[dict[str, Any]]:
    """Generate a short NPC quote with the fast small model while a dynamic scene loads."""
    del db  # reserved for future settings lookups
    chosen_npc = _pick_interlude_npc(candidate_npcs)
    if chosen_npc is None:
        return None
    llm_settings = dict(getattr(user, "llm_settings", None) or {})
    resolved = resolve_model_settings(llm_settings)
    provider = str(resolved["small_model_provider"])
    model = str(resolved["small_model"])

    if not _has_provider_credentials(user, provider):
        return None

    system_prompt, user_prompt = _build_interlude_prompts(
        adventure_title=adventure_title,
        adventure_setting=adventure_setting,
        adventure_tone=adventure_tone,
        origin_scene_name=origin_scene_name,
        exit_label=exit_label,
        zone_theme=zone_theme,
        chosen_npc=chosen_npc,
        language=language or "English",
    )

    try:
        llm = GameMasterLLM(user, provider=provider, model_category="small")
        payload = await llm.aexecute_complex_task(
            system_prompt,
            user_prompt,
            DynamicInterludeQuotePayload,
            model,
            adventure_id=adventure_id,
            game_id=game_id,
            operation="dynamic_scene.interlude_quote",
            phase="transition",
        )
        quote_text = _strip_outer_quotes(payload.quote)[:260]
        if not quote_text:
            return None
        speaker = chosen_npc["name"] if chosen_npc else (payload.speaker or "Voice in the Mist")
        role = (
            str(chosen_npc.get("role") or payload.role or "")
            if chosen_npc
            else str(payload.role or "")
        )
        image_url = chosen_npc.get("image_url") if chosen_npc else None
        return {
            "quote": quote_text,
            "speaker_name": speaker,
            "speaker_role": role,
            "npc_id": chosen_npc.get("id") if chosen_npc else None,
            "voice": chosen_npc.get("voice") if chosen_npc else None,
            "image_url": image_url,
            "speaker": speaker,
            "role": role,
            "avatar_url": image_url,
        }
    except Exception as exc:
        logger.debug("Dynamic interlude quote skipped due to error: %s", exc)
        return None


_NPC_SLOT_TYPES: tuple[tuple[str, str], ...] = (
    ("humanoid", "HUMANOID"),
    ("being", "BEING"),
    ("animal", "ANIMAL"),
    ("monster", "MONSTER"),
)


def _roll_npc_slots(
    target_npcs: int,
    npc_type_caps: dict[str, int],
    spawn_chances: dict[str, int],
    effective_danger: str,
) -> list[dict[str, str]]:
    """Roll per-NPC type and attitude slots respecting caps and spawn probabilities."""
    counts = {key: 0 for key, _ in _NPC_SLOT_TYPES}
    slots: list[dict[str, str]] = []
    for _ in range(target_npcs):
        available = [
            (key, label) for key, label in _NPC_SLOT_TYPES if counts[key] < npc_type_caps[key]
        ]
        if not available:
            break
        weights = [max(0, int(spawn_chances.get(key, 0))) for key, _ in available]
        if sum(weights) <= 0:
            break
        chosen_key, chosen_label = random.choices(available, weights=weights, k=1)[0]
        counts[chosen_key] += 1
        is_hostile = (
            effective_danger != "peaceful" and random.random() * 100 < spawn_chances["enemy"]
        )
        slots.append(
            {
                "npc_type": chosen_label,
                "attitude": "hostile" if is_hostile else "neutral",
            }
        )
    return slots


def _apply_cluster_node_floors(
    npc_slots: list[dict[str, str]],
    allow_items: bool,
    target_objects: int,
    *,
    zone: dict[str, Any],
    effective_danger: str,
    npc_allowed: bool,
    max_npcs: int,
    spawn_chances: dict[str, int],
    allowed_tokens: set[str],
) -> tuple[list[dict[str, str]], bool, int]:
    """Guarantee obstacle/branch blueprint roles have needed hostiles or loot."""
    cluster_node = zone.get("cluster_node")
    if not isinstance(cluster_node, dict):
        return npc_slots, allow_items, target_objects
    role = str(cluster_node.get("role") or "").lower()
    can_spawn_enemy = (
        effective_danger != "peaceful"
        and npc_allowed
        and max_npcs > 0
        and spawn_chances["npc"] > 0
        and spawn_chances["enemy"] > 0
    )
    if role == "obstacle" and can_spawn_enemy:
        if not npc_slots:
            npc_slots = [{"npc_type": "HUMANOID", "attitude": "hostile"}]
        elif not any(slot["attitude"] == "hostile" for slot in npc_slots):
            npc_slots[0]["attitude"] = "hostile"
    if role in {"obstacle", "branch"} and "OBJECT" in allowed_tokens and spawn_chances["item"] > 0:
        allow_items = True
        target_objects = max(1, target_objects)
    return npc_slots, allow_items, target_objects


def _roll_scene_plan(
    zone: dict[str, Any],
    max_npcs: int,
    effective_danger: str = "medium",
    generation_config: Optional[dict[str, Any]] = None,
    cluster_context: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Roll per-scene NPC and object composition targets from caps and spawn chances."""
    depth = int(zone.get("depth") or 1)
    max_depth = int(zone.get("max_depth") or 3)
    cul_de_sac = bool(zone.get("cul_de_sac_on_max_depth", True))
    is_climax = depth >= max_depth and cul_de_sac

    npc_type_caps, spawn_chances = resolve_effective_dynamic_rules(zone, generation_config)
    allowed_tokens = {
        str(token or "").strip().upper()
        for token in (zone.get("allowed_entity_types") or ["NPC", "OBJECT", "CONTAINER", "SWITCH"])
    }
    npc_allowed = bool(allowed_tokens & {"NPC", "FRIENDLY_NPC", "HOSTILE_NPC"})
    npc_roll_passes = (
        npc_allowed
        and max_npcs > 0
        and spawn_chances["npc"] > 0
        and random.random() * 100 < spawn_chances["npc"]
    )
    rolled_npcs = random.randint(1, max_npcs) if npc_roll_passes else 0
    npc_slots = _roll_npc_slots(rolled_npcs, npc_type_caps, spawn_chances, effective_danger)
    if is_climax and effective_danger != "peaceful" and npc_allowed and max_npcs > 0:
        if not npc_slots:
            npc_slots = [{"npc_type": "MONSTER", "attitude": "hostile"}]
        elif not any(slot["attitude"] == "hostile" for slot in npc_slots):
            npc_slots[0]["attitude"] = "hostile"

    allow_container = ("CONTAINER" in allowed_tokens) and (
        is_climax
        or (spawn_chances["container"] > 0 and random.random() * 100 < spawn_chances["container"])
    )
    allow_switch = (
        ("SWITCH" in allowed_tokens)
        and (not allow_container)
        and spawn_chances["switch"] > 0
        and random.random() * 100 < spawn_chances["switch"]
    )
    has_hostile_slot = any(slot["attitude"] == "hostile" for slot in npc_slots)
    needs_zone_key = has_hostile_slot and not is_climax and ("OBJECT" in allowed_tokens)
    allow_items = (
        is_climax
        or needs_zone_key
        or (spawn_chances["item"] > 0 and random.random() * 100 < spawn_chances["item"])
    )

    if allow_items:
        target_objects = max(2, random.randint(2, 3)) if is_climax else random.randint(1, 3)
    elif allow_container or allow_switch:
        target_objects = 1
    else:
        target_objects = 0

    npc_slots, allow_items, target_objects = _apply_cluster_node_floors(
        npc_slots,
        allow_items,
        target_objects,
        zone=zone,
        effective_danger=effective_danger,
        npc_allowed=npc_allowed,
        max_npcs=max_npcs,
        spawn_chances=spawn_chances,
        allowed_tokens=allowed_tokens,
    )

    allowed_item_types = (
        ["STANDARD", "CONSUMABLE", "WEARABLE", "WEAPON", "READABLE"] if allow_items else []
    )
    if allow_container:
        allowed_item_types.append("CONTAINER")
    if allow_switch:
        allowed_item_types.append("SWITCH")

    plan = adjust_plan_for_instructions(
        {
            "target_npcs": len(npc_slots),
            "npc_slots": npc_slots,
            "npc_type_caps": npc_type_caps,
            "allow_hostile": effective_danger != "peaceful" and spawn_chances["enemy"] > 0,
            "target_objects": target_objects,
            "allow_container": allow_container,
            "allow_switch": allow_switch,
            "allow_items": allow_items,
            "allowed_item_types": allowed_item_types,
            "is_climax": is_climax,
            "has_instructions": False,
        },
        zone,
        cluster_context,
    )
    return raise_plan_for_required(plan, required_blocks(zone, cluster_context))


def _filter_planned_npcs(
    npcs: list[Any],
    scene_plan: dict[str, Any],
) -> list[Any]:
    """Enforce target_npcs, per-type caps, and hostility rules on generated NPCs."""
    caps = dict(scene_plan.get("npc_type_caps") or {})
    allow_hostile = bool(scene_plan.get("allow_hostile", True))
    type_counts = {"humanoid": 0, "being": 0, "animal": 0, "monster": 0}
    filtered = []
    for npc in list(npcs or []):
        if len(filtered) >= int(scene_plan["target_npcs"]):
            break
        key = str(npc.npc_type or "HUMANOID").strip().lower()
        key = key if key in type_counts else "humanoid"
        if caps and type_counts[key] >= int(caps.get(key, 5)):
            continue
        type_counts[key] += 1
        if not allow_hostile and npc.attitude == "hostile":
            npc.attitude = "neutral"
            npc.combat_role = "none"
        filtered.append(npc)
    return filtered


def _apply_scene_plan_to_payload(
    payload: DynamicGeneratedScenePayload,
    scene_plan: dict[str, Any],
    zone: Optional[dict[str, Any]] = None,
    cluster_context: Optional[list[dict[str, Any]]] = None,
) -> set[str]:
    """Enforce rolled NPC/object limits, per-type caps, hostility, and item stats. The
    author-placed zone entities are added and survive every cut; returns their keys."""
    protected: set[str] = set()
    if zone:
        apply_instructions_backfill(payload, zone, scene_plan, cluster_context)
        protected = merge_required_entities(payload, required_blocks(zone, cluster_context))
    own_npcs, other_npcs = split_protected(list(payload.npcs or []), protected)
    npc_plan = {**scene_plan, "target_npcs": int(scene_plan["target_npcs"]) - len(own_npcs)}
    payload.npcs = [*own_npcs, *_filter_planned_npcs(other_npcs, npc_plan)]

    max_cap = 5
    carried_ids = {
        re.sub(r"[^A-Z0-9]+", "_", str(item_id or "").strip().upper()).strip("_")
        for npc in (payload.npcs or [])
        for item_id in (npc.inventory or [])
    }
    own_objects, other_objects = split_protected(list(payload.objects or []), protected)
    sliced_objects = own_objects + select_planned_objects(
        other_objects,
        int(scene_plan["target_objects"]) - len(own_objects),
        max_cap=max_cap - len(own_objects),
        carried_ids=carried_ids,
    )
    allow_switch = bool(scene_plan["allow_switch"])
    allow_container = bool(scene_plan["allow_container"])
    seen_switch = False
    seen_container = False

    for obj in sliced_objects:
        if is_protected(obj, protected):
            ensure_object_item_stats(obj)
            continue
        if obj.item_type == "SWITCH":
            obj.item_type = "STANDARD" if (not allow_switch or seen_switch) else "SWITCH"
            seen_switch = seen_switch or (obj.item_type == "SWITCH")
        elif obj.item_type == "CONTAINER":
            obj.item_type = "STANDARD" if (not allow_container or seen_container) else "CONTAINER"
            seen_container = seen_container or (obj.item_type == "CONTAINER")
        ensure_object_item_stats(obj)

    payload.objects = sliced_objects
    return protected


def _build_scene_prompts(
    *,
    adventure_title: str,
    adventure_setting: str,
    adventure_tone: str,
    origin_scene_name: str,
    origin_scene_description: str,
    exit_label: str,
    zone: dict[str, Any],
    language: str,
    effective_danger: str,
    max_npcs: int,
    scene_plan: dict[str, Any],
    cluster_context: Optional[list[dict[str, Any]]] = None,
    existing_scene_hint: Optional[dict[str, Any]] = None,
) -> tuple[str, str]:
    depth = int(zone.get("depth") or 1)
    max_depth = int(zone.get("max_depth") or 3)
    cul_de_sac = bool(zone.get("cul_de_sac_on_max_depth", True))
    is_climax = depth >= max_depth and cul_de_sac
    allowed = ", ".join(
        zone.get("allowed_entity_types") or ["NPC", "OBJECT", "CONTAINER", "SWITCH"]
    )

    if is_climax:
        depth_rule = (
            f"CLIMAX DEPTH ({depth}/{max_depth}): This is the end of the zone (cul-de-sac). "
            "Set forward_exits to an empty list []. Provide a memorable climax (reward container, lore discovery, or boss/guardian encounter)."
        )
        if existing_scene_hint:
            depth_rule += " Set forward_exits to []."
    elif existing_scene_hint:
        depth_rule = "PRE-MAPPED DYNAMIC SCENE: Set forward_exits to [] (map exits are already defined by the author)."
    else:
        depth_rule = f"EXPANSION DEPTH ({depth}/{max_depth}): Include 1 concise forward_exits entry leading deeper into the zone."

    target_npcs = int(scene_plan["target_npcs"])
    npc_slots = list(scene_plan.get("npc_slots") or [])
    target_objects = int(scene_plan["target_objects"])
    allowed_item_types = ", ".join(scene_plan["allowed_item_types"])

    if target_npcs <= 0:
        npc_rule = "- Do NOT spawn any NPCs in this scene (set npcs to an empty list [])."
    else:
        slot_desc = "; ".join(
            f"#{idx + 1}: npc_type={slot['npc_type']}, attitude={slot['attitude']}"
            for idx, slot in enumerate(npc_slots)
        )
        npc_rule = f"- Spawn EXACTLY {target_npcs} NPC(s) matching the zone theme" + (
            f" following these rolled slots: {slot_desc}." if slot_desc else "."
        )
    object_rule = (
        "\n- Do NOT spawn any interactable objects in this scene (set objects to an empty list [])."
        if target_objects <= 0
        else (
            f"\n- Spawn 1 to {target_objects} object(s) using ONLY these item_type values: {allowed_item_types}. "
            "Do NOT spawn a CONTAINER or SWITCH unless listed there, and at most 1 CONTAINER or SWITCH per scene. "
            "If you place item(s) inside a CONTAINER, include both the CONTAINER and each child object in `objects`, "
            "and list the child object ID(s) in the container's `inventory` field.\n"
            "- MIXED LOOT & ITEM STATS: Mix useful gear/consumables with occasional flavor trinkets (STANDARD/READABLE with 0 stats). "
            "For CONSUMABLE items set hp_change, stamina_change, or mana_change (e.g. 20 to 35). "
            "For WEARABLE items set wearable_slots (e.g. ['Ring'], ['Neck'], ['Head'], ['Chest'], ['Hands'], ['Feet']) and 1-2 light stat modifiers (+1 or +2 on strength/dexterity/intelligence/wisdom/charisma/armor_class). "
            "For WEAPON items set damage_dice (e.g. '1d8+1', '2d6+2', or '2d8+2') and optional +1 stat modifier."
        )
    )
    peaceful_rule = (
        "\n- PEACEFUL SCENE: Do NOT spawn hostile NPCs. Every NPC must have attitude 'friendly' or 'neutral' and combat_role 'none'."
        if effective_danger == "peaceful"
        else ""
    )
    speech_rule = (
        f"\n- NPC SPEECH RULE: Set npc_type to 'HUMANOID', 'BEING', 'ANIMAL', or 'MONSTER'. "
        f"Every HUMANOID or BEING NPC MUST speak normal, intelligible full sentences in {language} so the player can converse with them freely "
        f"(even if the main adventure features a mute, gesture-only, or fictional-dialect faction — make dynamic humanoids outsiders, travelers, or speakers who use plain {language}). "
        "Never give humanoid NPCs a dialogue_style of grunts, single syllables, or non-verbal sounds."
    )
    boss_role = "elite" if effective_danger == "low" else "boss"
    challenge_rule = (
        "\n- PACKS, LOOT, COMPANIONS & PUZZLES:\n"
        "  * Enemy packs & aggression: For hostile 'minion' or 'standard' NPCs (when danger is medium/high/deadly), you may set `clone_count` (2 to 4) to spawn a pack without inventing extra NPC entries. Set `attack_mode='ATTACK_ON_SIGHT'` on ambush/aggressive enemies that attack immediately on entry (keep others 'PASSIVE').\n"
        "  * Optional dynamic companions: Occasionally mark a friendly or neutral wanderer, mercenary, or creature (`HUMANOID`/`BEING`/`ANIMAL`) with `is_recruitable_companion=True` (and `companion_tactics` / `companion_banter`) so the player can recruit them.\n"
        "  * Enemy loot & keys: Hostile NPCs may carry loot or a key from `objects` in `npc.inventory` (dropped on defeat). On non-climax depths with enemies, include a key item in `objects` with `is_zone_key=True` whose form, name, and `visual_description` fit the Adventure Tone and Zone Theme, and list its ID in one hostile NPC's `inventory`.\n"
        "  * Simple scripted puzzles: For a SWITCH or puzzle prop, you may set `on_interact_script` using sandboxed `tw` calls such as `tw.objects.unlock('CHEST_ID')`, `tw.objects.reveal('HIDDEN_ID')`, `tw.story.narrate('...')` (no imports, no dunders, no `_` names; mark hidden rewards `is_hidden=True`)."
    )
    if is_climax and effective_danger != "peaceful":
        challenge_rule += (
            f"\n  * CLIMAX BOSS & LOOTBOX: Include a hostile `{boss_role}` NPC (`combat_role='{boss_role}'`) AND a reward `CONTAINER` chest with valuable loot in `inventory`. "
            "If an earlier scene in the cluster has a key item (or if you include one), lock the reward chest with `is_locked=True`, `item_to_unlock=<KEY_ID>`, and `lock_description`."
        )

    system_prompt = (
        "You are TaleWeaver's procedural location generator.\n"
        f"Generate ONE cohesive, self-contained scene matching the adventure tone, written strictly in {language}.\n"
        "STRICT LORE & QUEST ISOLATION RULES:\n"
        "- NEVER invent or spawn main-quest key items or break existing adventure puzzles.\n"
        "- NEVER spawn, duplicate, or kill named core story NPCs.\n"
        "- Keep visual_description and music_prompt in concise English (comma-separated visual/audio descriptors) even when narration text is in another language.\n"
        "- Keep entity IDs short uppercase alphanumeric slugs (e.g. RUSTY_PICKAXE, CAVE_SPIDER).\n"
        f"{npc_rule}{object_rule}{peaceful_rule}{speech_rule}{challenge_rule}"
    )
    blueprint_section = build_cluster_blueprint_prompt_section(zone)
    cluster_section = build_cluster_consistency_prompt_section(zone, cluster_context)
    instructions_section = build_instructions_prompt_section(zone, cluster_context)
    scene_hint_section = build_existing_scene_context_prompt_section(existing_scene_hint)
    required_section = required_prompt_section(required_blocks(zone, cluster_context))
    extra_sections = "\n\n".join(
        part
        for part in (
            blueprint_section,
            cluster_section,
            scene_hint_section,
            instructions_section,
            required_section,
        )
        if part
    )
    user_prompt = (
        f"Adventure Title: {adventure_title}\n"
        f"Adventure Tone: {adventure_tone or 'Atmospheric'}\n"
        f"Setting Context: {adventure_setting[:500]}\n"
        f"Origin Scene: {origin_scene_name} — {origin_scene_description[:280]}\n"
        f"Traversed Passage: {exit_label}\n"
        f"Zone ID: {zone['zone_id']}\n"
        f"Zone Theme: {zone['theme']}\n"
        f"Danger Level: {effective_danger}\n"
        f"Max NPCs Cap: {max_npcs} (Rolled target: {target_npcs})\n"
        f"Allowed Entity Types: {allowed}\n"
        f"{depth_rule}\n"
        f"{extra_sections}"
    ).strip()
    return system_prompt, user_prompt


def _build_fallback_scene_payload(
    exit_label: str,
    zone: dict[str, Any],
) -> DynamicGeneratedScenePayload:
    """Deterministic atmospheric fallback when no LLM is configured or generation fails."""
    depth = int(zone.get("depth") or 1)
    max_depth = int(zone.get("max_depth") or 3)
    cul_de_sac = bool(zone.get("cul_de_sac_on_max_depth", True))
    clean_zone = re.sub(r"[_-]+", " ", str(zone.get("zone_id") or "uncharted")).title()
    passage_hint = exit_label.strip() or "a weathered passage"
    forward = (
        []
        if depth >= max_depth and cul_de_sac
        else [
            {
                "label": f"A deeper trail into {clean_zone}",
                "theme_hint": str(zone.get("theme") or clean_zone),
            }
        ]
    )
    return DynamicGeneratedScenePayload.model_validate(
        {
            "name": f"{clean_zone} (Depth {depth})",
            "description": (
                f"Beyond {passage_hint}, the air shifts as you enter an uncharted reach shaped by {zone['theme']}. "
                "Shadows cling to weathered surfaces, and every footstep echoes into the unknown."
            ),
            "visual_description": f"{zone['theme']}, moody atmospheric lighting, detailed environment",
            "music_prompt": f"Atmospheric ambient underscore for {zone['theme']}, subtle tension, seamless loop",
            "npcs": [],
            "objects": [],
            "forward_exits": forward,
        }
    )


def _sync_forward_exits_with_blueprint(
    payload: DynamicGeneratedScenePayload,
    zone: dict[str, Any],
    existing_scene_hint: Optional[dict[str, Any]],
) -> None:
    """Align entry scene forward exits with planned outgoing edges on its cluster node."""
    if existing_scene_hint or int(zone.get("depth") or 1) >= int(zone.get("max_depth") or 3):
        return
    cluster_node = zone.get("cluster_node")
    if not isinstance(cluster_node, dict):
        return
    outgoing = list(cluster_node.get("outgoing_exits") or [])
    if not outgoing:
        return
    current = list(payload.forward_exits or [])
    synced: list[DynamicGeneratedChildExit] = []
    for idx, edge in enumerate(outgoing[:2]):
        cand = current[idx] if idx < len(current) else None
        label = str(getattr(cand, "label", "") or edge.get("label") or "Passage")[:100]
        hint = str(getattr(cand, "theme_hint", "") or edge.get("theme_hint") or "")[:300]
        synced.append(DynamicGeneratedChildExit(label=label, theme_hint=hint))
    payload.forward_exits = synced


def _finalize_fallback_scene(
    exit_label: str,
    zone: dict[str, Any],
    existing_scene_hint: Optional[dict[str, Any]],
    cluster_context: Optional[list[dict[str, Any]]] = None,
    *,
    backfill: bool = False,
) -> DynamicGeneratedScenePayload:
    """Build fallback payload, clearing exits on pre-mapped scenes and optionally backfilling."""
    fallback = _build_fallback_scene_payload(exit_label, zone)
    if existing_scene_hint:
        fallback.forward_exits = []
        fallback.name = str(existing_scene_hint.get("label") or fallback.name)[:100]
    else:
        _sync_forward_exits_with_blueprint(fallback, zone, existing_scene_hint)
    if backfill:
        apply_instructions_backfill(fallback, zone, {}, cluster_context)
    # Author-placed zone entities appear even when the generation failed.
    merge_required_entities(fallback, required_blocks(zone, cluster_context))
    return fallback


def _apply_peaceful_filter(npcs: list[Any]) -> None:
    """Ensure no hostile combat roles or attitudes appear in peaceful zones."""
    for npc in npcs:
        npc.combat_role = "none"
        if npc.attitude == "hostile":
            npc.attitude = "neutral"


async def generate_dynamic_scene_payload(
    *,
    adventure_title: str,
    adventure_setting: str,
    adventure_tone: str,
    origin_scene_name: str,
    origin_scene_description: str,
    exit_label: str,
    dynamic_zone: dict[str, Any],
    user: Any,
    db: AsyncSession,
    adventure_id: Optional[str] = None,
    game_id: Optional[str] = None,
    language: str = "English",
    max_npcs_default: int = 2,
    generation_config: Optional[dict[str, Any]] = None,
    cluster_context: Optional[list[dict[str, Any]]] = None,
    existing_scene_hint: Optional[dict[str, Any]] = None,
) -> DynamicGeneratedScenePayload:
    """Generate a structured DynamicGeneratedScenePayload via LLM with deterministic fallback."""
    del db
    zone = normalize_dynamic_zone(dynamic_zone)
    if not zone:
        raise ValueError("Cannot generate a dynamic scene without a valid dynamic_zone config.")

    raw_danger = str(zone.get("danger_level") or "medium")
    effective_danger = (
        random.choice(_RANDOM_DANGER_CHOICES) if raw_danger == "random" else raw_danger
    )
    raw_max_npcs = dynamic_zone.get("max_npcs") if isinstance(dynamic_zone, dict) else None
    max_npcs = int(zone["max_npcs"] if raw_max_npcs is not None else max_npcs_default)
    max_npcs = max(0, min(5, max_npcs))

    provider, model, model_category = resolve_dynamic_llm_model(user, zone, generation_config)

    if not _has_provider_credentials(user, provider):
        logger.info("No LLM credentials for provider %s; using fallback dynamic scene.", provider)
        return _finalize_fallback_scene(
            exit_label, zone, existing_scene_hint, cluster_context, backfill=True
        )

    scene_plan = _roll_scene_plan(
        zone,
        max_npcs,
        effective_danger=effective_danger,
        generation_config=generation_config,
        cluster_context=cluster_context,
    )
    system_prompt, user_prompt = _build_scene_prompts(
        adventure_title=adventure_title,
        adventure_setting=adventure_setting,
        adventure_tone=adventure_tone,
        origin_scene_name=origin_scene_name,
        origin_scene_description=origin_scene_description,
        exit_label=exit_label,
        zone=zone,
        language=language or "English",
        effective_danger=effective_danger,
        max_npcs=max_npcs,
        scene_plan=scene_plan,
        cluster_context=cluster_context,
        existing_scene_hint=existing_scene_hint,
    )

    try:
        llm = GameMasterLLM(user, provider=provider, model_category=model_category)
        payload = await llm.aexecute_complex_task(
            system_prompt,
            user_prompt,
            DynamicGeneratedScenePayload,
            model,
            adventure_id=adventure_id,
            game_id=game_id,
            operation="dynamic_scene.generate",
            phase="expansion",
        )
        protected = _apply_scene_plan_to_payload(payload, scene_plan, zone, cluster_context)
        payload.npcs = cap_npcs(payload.npcs, max_npcs, protected)
        if effective_danger == "peaceful":
            _apply_peaceful_filter(payload.npcs)
        is_cul_de_sac = int(zone["depth"]) >= int(zone["max_depth"]) and zone.get(
            "cul_de_sac_on_max_depth"
        )
        if existing_scene_hint or is_cul_de_sac:
            payload.forward_exits = []
        else:
            _sync_forward_exits_with_blueprint(payload, zone, existing_scene_hint)
        return payload
    except Exception as exc:
        logger.warning("Dynamic scene generation failed (%s); using fallback scene.", exc)
        return _finalize_fallback_scene(exit_label, zone, existing_scene_hint, cluster_context)
