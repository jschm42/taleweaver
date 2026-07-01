"""
Prompt construction for the world generation LLM call.

This module builds the system and user prompts for `WorldGenerator.generate_world`
based on the generation parameters (scene/quest/award/container/item counts, tone,
cover-source guidance, etc.).
"""
from typing import Any, Optional

from backend.core import prompts


def _build_voice_assignment_requirement(
    enabled: bool,
    available_voice_list: Optional[list[str]] = None,
) -> str:
    """Return voice assignment instructions for the LLM prompt (currently a no-op placeholder)."""
    return ""


def _build_scene_requirement(min_scenes: Optional[int], max_scenes: Optional[int]) -> str:
    if min_scenes is None and max_scenes is None:
        return "- Generate a suitable number of unique scenes (typically between 3 and 10) based on the story complexity."
    if min_scenes is not None and max_scenes is None:
        return f"- Generate at least {max(1, min_scenes)} unique scenes."
    if min_scenes is None and max_scenes is not None:
        return f"- Generate no more than {max(1, max_scenes)} unique scenes."
    return f"- Generate between {max(1, min_scenes)} and {max(1, max_scenes)} unique scenes."  # type: ignore[arg-type]


def _build_quest_requirement(
    quest_generation_enabled: bool,
    min_quests: Optional[int],
    max_quests: Optional[int],
) -> str:
    if not quest_generation_enabled:
        return "\n- Do not generate any quests for this adventure."
    if min_quests is None and max_quests is None:
        return "\n- Generate a suitable number of total quests (typically between 2 and 6) that fit the narrative context. Mix main and side quests naturally."
    if min_quests is not None and max_quests is None:
        return f"\n- Generate at least {max(1, min_quests)} total quests. Mix main and side quests naturally."
    if min_quests is None and max_quests is not None:
        return f"\n- Generate no more than {max(1, max_quests)} total quests. Mix main and side quests naturally."
    clamped_min = max(1, min(30, int(min_quests)))  # type: ignore[arg-type]
    clamped_max = max(clamped_min, min(30, int(max_quests)))  # type: ignore[arg-type]
    return (
        f"\n- Generate between {clamped_min} and {clamped_max} total quests that fit the narrative context."
        " Mix main and side quests naturally."
    )


def _build_award_requirement(
    award_generation_enabled: bool,
    min_awards: Optional[int],
    max_awards: Optional[int],
) -> str:
    if not award_generation_enabled:
        return "\n\nAWARD SYSTEM:\n- Do not generate any awards for this adventure."
    if min_awards is None and max_awards is None:
        return "\n\nAWARD SYSTEM:\n- Generate a suitable number of unique Awards (typically between 3 and 8) that players can earn."
    if min_awards is not None and max_awards is None:
        return f"\n\nAWARD SYSTEM:\n- Generate at least {max(1, min_awards)} unique Awards that players can earn."
    if min_awards is None and max_awards is not None:
        return f"\n\nAWARD SYSTEM:\n- Generate no more than {max(1, max_awards)} unique Awards that players can earn."
    clamped_min = max(1, min(30, int(min_awards)))  # type: ignore[arg-type]
    clamped_max = max(clamped_min, min(30, int(max_awards)))  # type: ignore[arg-type]
    return f"\n\nAWARD SYSTEM:\n- Generate between {clamped_min} and {clamped_max} unique Awards that players can earn."


_CONTAINER_LOCK_HINTS = (
    "- CONTAINER objects may be open or locked depending on story needs.\n"
    "- Use lock mechanics frequently for containers that imply security/value (e.g. safe, strongbox, lockbox, vault, sealed crate, lootbox with lock).\n"
    "- For locked containers, provide deterministic `code_to_unlock` and/or `item_to_unlock`; for open containers, keep both empty.\n"
    "- CRITICAL: NEVER write the unlock code directly in plain text in a single note/log (e.g., 'The code is 1234'). That is boring and provides no challenge!\n"
    "- Instead, hide the `code_to_unlock` behind one of these three patterns:\n"
    "  1. RIDDLES & PUZZLES: The code is the answer to a math or logic puzzle. Place this riddle in a READABLE text log or a description. Use counting puzzles (e.g., 'Count the pillars in the hall and multiply by the candles'), wordplay, or math based on lore numbers.\n"
    "  2. SPLIT CODES (FRAGMENTS): Break the code into 2 or 3 parts (e.g. 'First part: 45', 'Second part: 89' making '4589') and distribute them across different READABLE objects (e.g., sign, book, scroll) or scene details in different locations.\n"
    "  3. NPC COAXING / INTERROGATION: An NPC knows the code or a clue. The player must talk to them, negotiate, bribe, or help them to get the code or clue. Put this in the NPC's biography/reveal_rule or give them a READABLE item in their inventory.\n"
    "- Explain the exact solution and clues for each container lock in the secret GM `walkthrough`.\n"
    "- CONTAINER LOCK INVARIANT (CRITICAL): The engine sets `metadata_json.locked` to true only when at least one of `code_to_unlock`, `item_to_unlock`, or `rule_to_unlock` is non-empty. Therefore: if the description says the container is locked, requires a code/key/password/combination, or otherwise cannot be opened freely, you MUST set exactly one of those three unlock fields — never describe a lock in prose without binding it to a deterministic unlock field. If the container is open and freely searchable, keep all three fields empty."
)

_CONTAINER_NON_EMPTY_HINT = "\n- Every generated CONTAINER must include at least one item ID in `inventory`; do not leave container inventories empty."


def _build_container_requirement(
    container_generation_enabled: bool,
    min_containers: Optional[int],
    max_containers: Optional[int],
) -> str:
    if not container_generation_enabled:
        return "\n\nCONTAINER ITEMS:\n- Do not generate any objects with item_type CONTAINER."

    if min_containers is None and max_containers is None:
        body = (
            "- Generate a suitable number of container items (typically between 2 and 6) if the scenes require them.\n"
            + _CONTAINER_LOCK_HINTS
        )
    elif min_containers is not None and max_containers is None:
        body = f"- Generate at least {max(0, min_containers)} container items.\n" + _CONTAINER_LOCK_HINTS
    elif min_containers is None and max_containers is not None:
        body = f"- You may generate CONTAINER objects, but never more than {max(0, max_containers)}.\n" + _CONTAINER_LOCK_HINTS
    else:
        body = (
            f"- Generate between {max(0, min_containers)} and {max(0, max_containers)} container items.\n"  # type: ignore[arg-type]
            + _CONTAINER_LOCK_HINTS
        )

    return f"\n\nCONTAINER ITEMS:\n{body}{_CONTAINER_NON_EMPTY_HINT}"


def _build_text_log_requirement(
    text_log_generation_enabled: bool,
    min_text_logs: Optional[int],
    max_text_logs: Optional[int],
) -> str:
    if not text_log_generation_enabled:
        return "\n\nTEXT LOGS (READABLE OBJECTS):\n- Do not generate any READABLE objects."

    base = (
        "- For every READABLE object, provide `text_log_content` with at most 500 characters and `text_log_format` as DOCUMENT, SCROLL, BOOK, or SIGN.\n"
        "- `text_log_content` for READABLE objects MUST be non-empty (never \"\" and never omitted).\n"
        "- Keep text_log_content practical: hints, story fragments, warnings, clues. Paragraph formatting is allowed; use blank lines between paragraphs when useful.\n"
        "- CRITICAL FOR CLUES: If a READABLE contains information about a lock code, NEVER write the code directly (e.g. 'The code is 1234'). Write a riddle, a counting task (referencing decorative objects in a scene), a logic/math puzzle, or only a fragment of the full code (with other fragments located on other READABLE objects)."
    )

    if min_text_logs is None and max_text_logs is None:
        intro = "- Generate a suitable number of readable text logs (typically between 1 and 5) containing clues or lore.\n"
    elif min_text_logs is not None and max_text_logs is None:
        intro = f"- Generate at least {max(0, min_text_logs)} readable text logs.\n"
    elif min_text_logs is None and max_text_logs is not None:
        intro = f"- You may generate READABLE objects, but never more than {max(0, max_text_logs)}.\n"
    else:
        intro = f"- Generate between {max(0, min_text_logs)} and {max(0, max_text_logs)} readable text logs.\n"  # type: ignore[arg-type]

    return f"\n\nTEXT LOGS (READABLE OBJECTS):\n{intro}{base}"


def _build_item_requirement(min_items: Optional[int], max_items: Optional[int]) -> str:
    if min_items is None and max_items is None:
        return "\n\nITEM COUNT LIMIT:\n- Generate a suitable number of total objects/items in `objects` (typically between 5 and 25) that fit the scenes."
    if min_items is not None and max_items is None:
        return f"\n\nITEM COUNT LIMIT:\n- Generate at least {max(1, min_items)} total objects/items in `objects`."
    if min_items is None and max_items is not None:
        return f"\n\nITEM COUNT LIMIT:\n- Generate no more than {max(1, max_items)} total objects/items in `objects`."
    return f"\n\nITEM COUNT LIMIT:\n- Generate between {max(1, min_items)} and {max(1, max_items)} total objects/items in `objects`."  # type: ignore[arg-type]


def _build_switch_requirement(original_prompt: str) -> str:
    prompt_lower = str(original_prompt or "").lower()
    wants_switches = any(
        token in prompt_lower
        for token in ["switch", "switches", "lever", "control panel", "schalter", "hebel", "mechanism", "mechanik"]
    )
    if wants_switches:
        return (
            "\n\nSWITCH MECHANISMS:\n"
            "- Generate at least one object with item_type SWITCH if the story idea mentions a switch/lever/mechanism.\n"
            "- Every SWITCH must include switch_states (>=2), switch_initial_state, and switch_transitions.\n"
            "- Transition objects must use: from (optional — omit to apply regardless of current state), to, gates{item,code,rule}, fail_message.\n"
            "- Optionally include switch_outcomes with deterministic effects: unlock_exit, unlock_container, story_flag."
        )
    return (
        "\n\nSWITCH MECHANISMS:\n"
        "- You may generate item_type SWITCH for puzzle/mechanism interactions when narratively appropriate.\n"
        "- If used, include switch_states, switch_initial_state, and switch_transitions in deterministic form."
    )


def _build_cover_guidance(
    cover_source_manifest: Optional[dict[str, Any]],
    cover_source_adventure_name: Optional[str],
    cover_similarity_percent: int,
    allow_reuse_source_assets: bool,
) -> str:
    if not cover_source_manifest:
        return ""

    source_title = cover_source_adventure_name or cover_source_manifest.get("title") or "Unknown Source Adventure"
    source_description = (
        cover_source_manifest.get("teaser")
        or cover_source_manifest.get("original_prompt")
        or cover_source_manifest.get("plot")
        or ""
    )
    similarity = max(0, min(100, int(cover_similarity_percent or 0)))
    source_scene_ids = [
        s.get("id")
        for s in (cover_source_manifest.get("scenes") or [])
        if isinstance(s, dict) and s.get("id")
    ][:12]
    source_npc_ids = [
        n.get("id")
        for n in (cover_source_manifest.get("npcs") or [])
        if isinstance(n, dict) and n.get("id")
    ][:12]
    source_object_ids = [
        o.get("id")
        for o in (cover_source_manifest.get("objects") or [])
        if isinstance(o, dict) and o.get("id")
    ][:24]

    return (
        "\n\nCOVER MODE:\n"
        f"- Create this as a cover of '{source_title}'.\n"
        f"- Requested similarity: {similarity}% (0 = freely inspired, 100 = very close).\n"
        f"- Source summary: {source_description[:800]}\n"
        f"- Old asset reuse allowed: {'yes' if allow_reuse_source_assets else 'no'}.\n"
        "- Use the source IDs below to preserve motifs and mapping where useful.\n"
        "- If you intentionally want to reuse old visual assets, set `source_asset_id` on protagonist/scenes/npcs/objects entries to the chosen source IDs.\n"
        "- If you want to reuse the old cover image, set `cover_source_asset_id` to `COVER`.\n"
        f"- Source scene IDs (sample): {source_scene_ids}\n"
        f"- Source NPC IDs (sample): {source_npc_ids}\n"
        f"- Source object IDs (sample): {source_object_ids}\n"
    )


def build_world_generation_prompts(
    *,
    title: str,
    original_prompt: str,
    language: Optional[str],
    selected_tone: Optional[str],
    automatic_npc_voice_assignment: bool,
    available_voice_list: Optional[list[str]],
    can_damage_npcs: bool,
    npcs_can_damage_protagonist: bool,
    quest_generation_enabled: bool,
    min_scenes: Optional[int],
    max_scenes: Optional[int],
    min_quests: Optional[int],
    max_quests: Optional[int],
    award_generation_enabled: bool,
    min_awards: Optional[int],
    max_awards: Optional[int],
    container_generation_enabled: bool,
    min_containers: Optional[int],
    max_containers: Optional[int],
    text_log_generation_enabled: bool,
    min_text_logs: Optional[int],
    max_text_logs: Optional[int],
    min_items: Optional[int],
    max_items: Optional[int],
    cover_source_manifest: Optional[dict[str, Any]],
    cover_source_adventure_name: Optional[str],
    cover_similarity_percent: int,
    allow_reuse_source_assets: bool,
) -> tuple[str, str]:
    """Build the system and user prompts for the world generation LLM call.

    Returns:
        A tuple of ``(system_prompt, user_prompt)``.
    """
    system_prompt = prompts.WORLD_GENERATION_SYSTEM_PROMPT
    if language:
        system_prompt += (
            f"\n\nCRITICAL: You MUST generate all content (names, descriptions, teaser, plot, "
            f"intro_text, walkthrough, quests) in {language}. Do not use any other language."
        )
    if not quest_generation_enabled:
        system_prompt += "\n\nQUEST GENERATION OVERRIDE: Do not generate any quests for this adventure."

    scene_requirement = _build_scene_requirement(min_scenes, max_scenes)
    quest_requirement = _build_quest_requirement(quest_generation_enabled, min_quests, max_quests)
    award_requirement = _build_award_requirement(award_generation_enabled, min_awards, max_awards)
    cover_guidance = _build_cover_guidance(
        cover_source_manifest, cover_source_adventure_name, cover_similarity_percent, allow_reuse_source_assets
    )

    user_prompt = prompts.WORLD_GENERATION_USER_PROMPT_TEMPLATE.format(
        title=title,
        original_prompt=original_prompt,
        selected_tone=selected_tone or "Standard RPG",
        scene_requirement=scene_requirement,
        can_damage_npcs="true" if can_damage_npcs else "false",
        npcs_can_damage_protagonist="true" if npcs_can_damage_protagonist else "false",
        voice_assignment_requirement=_build_voice_assignment_requirement(
            automatic_npc_voice_assignment,
            available_voice_list,
        ),
        cover_guidance=cover_guidance,
        quest_requirement=quest_requirement,
        award_requirement=award_requirement,
        text_log_requirement=_build_text_log_requirement(
            text_log_generation_enabled, min_text_logs, max_text_logs
        ),
    )
    user_prompt += _build_container_requirement(container_generation_enabled, min_containers, max_containers)
    user_prompt += _build_item_requirement(min_items, max_items)
    user_prompt += _build_switch_requirement(original_prompt)

    return system_prompt, user_prompt
