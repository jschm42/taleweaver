"""System and user prompt of one procedural dynamic scene (room)."""

from __future__ import annotations

from typing import Any, Optional

from backend.engine.world.dynamic_cluster_blueprint import build_cluster_blueprint_prompt_section
from backend.engine.world.dynamic_instructions_helper import (
    build_cluster_consistency_prompt_section,
    build_existing_scene_context_prompt_section,
    build_instructions_prompt_section,
)
from backend.engine.world.dynamic_required_entities import (
    required_blocks,
    required_prompt_section,
)


def build_scene_prompts(
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
    """The (system, user) prompt for one room: plan rules, depth rule and context sections."""
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
