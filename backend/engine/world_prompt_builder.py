"""
Prompt construction for the world generation LLM call.

This module builds the system and user prompts for `WorldGenerator.generate_world`
based on the generation parameters (scene/quest/award/container/item counts, tone,
cover-source guidance, etc.).
"""

from typing import Any, Optional

from backend.core import prompts
from backend.engine.elevenlabs_voices import VoiceOption, load_voice_catalog
from backend.engine.world_scripting_prompt import build_scripts_requirement

_CONTAINER_LOCK_HINTS = (
    "- CONTAINER objects may be open or locked depending on story needs.\n"
    "- Use lock mechanics frequently for containers that imply security/value (e.g. safe, strongbox, lockbox, vault, sealed crate, lootbox with lock).\n"
    "- For locked containers, provide deterministic `code_to_unlock` and/or `item_to_unlock`; for open containers, keep both empty.\n"
    "- CRITICAL: NEVER write the unlock code directly in plain text in a single note/log (e.g., 'The code is 1234'). That is boring and provides no challenge!\n"
    "- Instead, hide the `code_to_unlock` behind one of these three patterns:\n"
    "  1. RIDDLES & PUZZLES: The code is the answer to a math or logic puzzle. Place this riddle in a READABLE text log or a description. Use counting puzzles (e.g., 'Count the pillars in the hall and multiply by the candles'), wordplay, or math based on lore numbers.\n"
    "  2. SPLIT CODES (FRAGMENTS): Break the code into 2 or 3 parts (e.g. 'First part: 45', 'Second part: 89' making '4589') and distribute them across different READABLE objects (e.g., sign, book, scroll) or scene details in different locations.\n"
    "  3. NPC COAXING / INTERROGATION: An NPC knows the code or a clue. The player must talk to them, negotiate, bribe, or help them to get the code or clue. Put this in the NPC's biography/reveal_rule or give them a READABLE item in their inventory.\n"
    "- Explain the exact solution and clues for each container lock in the dedicated `walkthrough` of the sequence where the container/lock is located (inside `sequences`).\n"
    "- CONTAINER LOCK INVARIANT (CRITICAL): The engine sets `metadata_json.locked` to true only when at least one of `code_to_unlock`, `item_to_unlock`, or `rule_to_unlock` is non-empty. Therefore: if the description says the container is locked, requires a code/key/password/combination, or otherwise cannot be opened freely, you MUST set exactly one of those three unlock fields — never describe a lock in prose without binding it to a deterministic unlock field. If the container is open and freely searchable, keep all three fields empty."
)


def _voice_register(voice: VoiceOption) -> str:
    raw = voice.get("gender")
    if raw == "female":
        return "female"
    if raw == "male":
        return "male"
    return ""


def _voice_line(voice: VoiceOption) -> str:
    traits = ", ".join(
        part
        for part in (_voice_register(voice), voice["age"], voice["accent"], voice["description"])
        if part
    )
    good_for = f"; good for {', '.join(voice['good_for'])}" if voice["good_for"] else ""
    return f"- {voice['id']}: {voice['name']} ({traits}{good_for})"


def _build_voice_assignment_requirement(enabled: bool) -> str:
    """Asks the world builder to give each NPC a fitting voice id from the voice list."""
    voices = load_voice_catalog()
    if not enabled or not voices:
        return ""
    voice_lines = "\n".join(_voice_line(voice) for voice in voices)
    return (
        "NPC VOICES:\n"
        "- Give every NPC and the protagonist a `voice` field with the id of the best-fitting voice "
        "from this list (match gender, age and personality). Use each voice for at most one character "
        "while unused voices remain.\n"
        "- Use ONLY ids from this list, exactly as written:\n"
        f"{voice_lines}\n\n"
    )


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


def _sequence_limit_text(min_sequences: Optional[int], max_sequences: Optional[int]) -> str:
    if min_sequences is None and max_sequences is None:
        return "typically between 3 and 7 sequences, maximum 15"
    if max_sequences is None:
        return f"at least {max(1, min_sequences or 1)} sequences, maximum 15"
    if min_sequences is None:
        return f"maximum {max(1, max_sequences)} sequences"
    return f"between {max(1, min_sequences)} and {max(1, max_sequences)} sequences"


def _creative_sequence_limit_text(
    min_sequences: Optional[int], max_sequences: Optional[int]
) -> str:
    bridge = "If the user provided fewer than {n} sequences, you MUST invent NEW sequences to bridge the gaps and meet the minimum! "
    if min_sequences is not None and max_sequences is not None:
        return (
            f"You MUST generate between {min_sequences} and {max_sequences} total sequences. "
            + bridge.format(n=min_sequences)
        )
    if min_sequences is not None:
        return f"You MUST generate at least {min_sequences} total sequences. " + bridge.format(
            n=min_sequences
        )
    if max_sequences is not None:
        return f"You MUST generate no more than {max_sequences} total sequences. "
    return "You MUST generate up to 15 total sequences. If the user provided only a few, you are highly encouraged to invent NEW sequences to expand the story! "


def _build_sequences_requirement(
    sequences: Optional[list[dict[str, Any]]],
    generation_strictness: str,
    min_sequences: Optional[int],
    max_sequences: Optional[int],
) -> str:
    if not sequences:
        seq_limit_text = _sequence_limit_text(min_sequences, max_sequences)

        return (
            "\n\n================================================================================\n"
            "STORY SEQUENCES (LINEAR CHAPTERS & DEDICATED WALKTHROUGHS):\n"
            f"- You MUST break the adventure's main storyline arc into a chronological series of linear chapters in `sequences` ({seq_limit_text}).\n"
            "- You MUST include ALL generated sequences in the `sequences` array of your JSON output! DO NOT leave it empty.\n"
            "- Each sequence represents a distinct narrative phase or chapter of the adventure (e.g. Chapter 1: The Awakening/Escape, Chapter 2: The Sewers, Chapter 3: The Sanctuary).\n"
            "- For EVERY sequence in `sequences`, you MUST populate:\n"
            "  * `id`: unique slug (e.g. 'SEQ_1_ESCAPE', 'SEQ_2_SEWERS')\n"
            "  * `order`: 1-based sequential integer (1, 2, 3...)\n"
            "  * `title`: evocative title of the chapter\n"
            "  * `description`: narrative guidelines and context for the GM during this sequence\n"
            "  * `walkthrough`: the DEDICATED, step-by-step walkthrough and puzzle solutions specifically for this sequence! How the player overcomes this chapter's obstacles, finds keys/codes, interacts with NPCs, and reaches the sequence objective.\n"
            "  * `end_condition`: technical or narrative condition to complete this sequence and unlock the next sequence (e.g. 'The player unlocks the iron gate with the brass key and enters the sewer tunnels')\n"
            "  * DETERMINISTIC HARD RULES (optional completion triggers, populate where applicable for clear mechanical progression):\n"
            "    - `required_item_id`: ID of an existing item the protagonist must obtain to complete this sequence (e.g. 'BRASS_KEY'). Empty string if no item trigger.\n"
            "    - `required_scene_id`: ID of an existing scene the protagonist must enter to complete this sequence (e.g. 'SEWER_TUNNELS'). Empty string if no scene trigger.\n"
            "    - `required_defeated_npc_id`: ID of an existing NPC the protagonist must defeat to complete this sequence (e.g. 'GOBLIN_WARLORD'). Empty string if no NPC defeat trigger.\n"
            "    - RULE INVARIANT: Any referenced item, scene, or NPC ID in hard rules MUST exist in your generated `objects`, `scenes`, or `npcs`!\n"
            "  * `exp_reward`: XP awarded upon completion (e.g. 50, 100, 200)\n"
            "- CRITICAL: All puzzle solutions and progression steps MUST be defined in their respective sequence's `walkthrough`.\n"
            "================================================================================\n"
        )

    strict_mode = generation_strictness == "strict"

    seq_text = (
        "The user has provided a structural blueprint consisting of the following Sequences. "
    )
    seq_text += f"HARD LIMIT: You must strictly enforce a maximum of 15 sequences in the final output. The user provided {len(sequences)} sequences.\n\n"

    if strict_mode:
        seq_text += "STRICT ADHERENCE MODE IS ACTIVE: You MUST strictly implement these sequences as the core backbone of the adventure. "
        seq_text += "Do not deviate from their order or core intent. Fill in the details, and provide the dedicated `walkthrough`, `end_condition`, hard rules, and `exp_reward` for each sequence.\n"
    else:
        seq_text += (
            "CREATIVE EXPANSION MODE IS ACTIVE: Use these sequences as a creative foundation. "
        )
        seq_text += "You are free to adapt, expand, or add intermediate sequences to create a richer narrative experience. "

        seq_text += _creative_sequence_limit_text(min_sequences, max_sequences)

        seq_text += "For every sequence, provide its dedicated `walkthrough`, `end_condition`, and applicable hard rules.\n"

    seq_text += "\nUser-Provided Sequences:\n"
    for s in sequences:
        reqs = []
        if s.get("required_item_id"):
            reqs.append(f"required_item_id='{s['required_item_id']}'")
        if s.get("required_scene_id"):
            reqs.append(f"required_scene_id='{s['required_scene_id']}'")
        if s.get("required_defeated_npc_id"):
            reqs.append(f"required_defeated_npc_id='{s['required_defeated_npc_id']}'")
        req_info = f" [Hard Rules: {', '.join(reqs)}]" if reqs else ""
        end_cond = f" [End Condition: {s.get('end_condition')}]" if s.get("end_condition") else ""
        seq_text += f"[{s.get('order', 0)}] {s.get('title', 'Unknown')}: {s.get('description', '')}{end_cond}{req_info}\n"

    seq_text += (
        "\nCRITICAL REQUIREMENT FOR SEQUENCES:\n"
        "- You MUST include ALL generated sequences in the `sequences` array of your JSON output! DO NOT leave it empty.\n"
        "- For EVERY sequence in `sequences`, you MUST populate:\n"
        "  * `id`: unique slug (e.g. 'SEQ_1_ESCAPE')\n"
        "  * `order`: sequential integer starting at 1\n"
        "  * `title`: chapter title\n"
        "  * `description`: narrative guidance and context for the GM during this sequence\n"
        "  * `walkthrough`: DEDICATED step-by-step walkthrough and puzzle solutions specifically for this sequence.\n"
        "  * `end_condition`: condition that triggers transition to the next sequence\n"
        "  * `required_item_id`: ID of item protagonist must obtain (or empty string)\n"
        "  * `required_scene_id`: ID of scene protagonist must enter (or empty string)\n"
        "  * `required_defeated_npc_id`: ID of NPC protagonist must defeat (or empty string)\n"
        "  * If the user provided hard rules above, you MUST preserve them and ensure the referenced IDs exist in your generated world entities/scenes.\n"
        "  * `exp_reward`: XP awarded upon sequence completion (e.g. 50, 100, 200)\n"
    )

    return f"\n\n================================================================================\n{seq_text}================================================================================\n"


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
        body = (
            f"- Generate at least {max(0, min_containers)} container items.\n"
            + _CONTAINER_LOCK_HINTS
        )
    elif min_containers is None and max_containers is not None:
        body = (
            f"- You may generate CONTAINER objects, but never more than {max(0, max_containers)}.\n"
            + _CONTAINER_LOCK_HINTS
        )
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
        '- `text_log_content` for READABLE objects MUST be non-empty (never "" and never omitted).\n'
        "- Keep text_log_content practical: hints, story fragments, warnings, clues. Paragraph formatting is allowed; use blank lines between paragraphs when useful.\n"
        "- CRITICAL FOR CLUES: If a READABLE contains information about a lock code, NEVER write the code directly (e.g. 'The code is 1234'). Write a riddle, a counting task (referencing decorative objects in a scene), a logic/math puzzle, or only a fragment of the full code (with other fragments located on other READABLE objects)."
    )

    if min_text_logs is None and max_text_logs is None:
        intro = "- Generate a suitable number of readable text logs (typically between 1 and 5) containing clues or lore.\n"
    elif min_text_logs is not None and max_text_logs is None:
        intro = f"- Generate at least {max(0, min_text_logs)} readable text logs.\n"
    elif min_text_logs is None and max_text_logs is not None:
        intro = (
            f"- You may generate READABLE objects, but never more than {max(0, max_text_logs)}.\n"
        )
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


_SWITCH_DETAILS_HINT = (
    "- Every SWITCH must include switch_states (>=2), switch_initial_state, and switch_transitions.\n"
    "- State IDs are script keys: 1-15 characters, upper-case letters, digits, '_' or '-' (e.g. 'OFF', 'HALF-OPEN', 'LEVEL_2'). "
    "For player-friendly text add `switch_state_labels` ({state, label}, label max 20 characters, e.g. {state: 'HALF-OPEN', label: 'Half open'}); without a label the ID is shown in-game.\n"
    "- Transition objects shape: {from (optional), to, gates{item,code,rule,expression}, fail_message, success_message, on_success_script, on_failure_script}.\n"
    "- Transition guards (`gates`):\n"
    "  * `item`: inventory item ID required to operate switch (e.g. 'RUSTY_KEY').\n"
    "  * `code`: passcode or sequence code required (e.g. '4711').\n"
    "  * `rule`: soft story flag required.\n"
    "  * `expression`: deterministic Python boolean expression evaluated with tw (e.g. \"tw.player.has_item('KEY')\" or \"tw.vars.get('power_on') == True\").\n"
    "- Transition and switch scripts: optionally provide `on_success_script` and `on_failure_script` for deterministic logic executed upon state changes.\n"
    "- Optionally include switch_outcomes with deterministic effects: unlock_exit, unlock_container, story_flag."
)


def _build_switch_requirement(original_prompt: str) -> str:
    prompt_lower = str(original_prompt or "").lower()
    switch_tokens = [
        "switch",
        "switches",
        "lever",
        "control panel",
        "schalter",
        "hebel",
        "mechanism",
        "mechanik",
    ]
    wants_switches = any(token in prompt_lower for token in switch_tokens)
    if wants_switches:
        return (
            "\n\nSWITCH MECHANISMS:\n"
            "- Generate at least one object with item_type SWITCH if the story idea mentions a switch/lever/mechanism.\n"
            f"{_SWITCH_DETAILS_HINT}"
        )
    return (
        "\n\nSWITCH MECHANISMS:\n"
        "- You may generate item_type SWITCH for puzzle/mechanism interactions when narratively appropriate.\n"
        f"{_SWITCH_DETAILS_HINT}"
    )


def _build_special_attack_requirement(
    can_damage_npcs: bool, npcs_can_damage_protagonist: bool
) -> str:
    """Explains configurable special attacks so the world builder can design memorable fights."""
    if not (can_damage_npcs or npcs_can_damage_protagonist):
        return ""
    return (
        "\n\nSPECIAL ATTACKS (turn-based combat): give the protagonist 2-4 and hostile NPCs 1-3 "
        "`special_actions` that fit the story. They can be classic spells (MAGIC), weapon techniques "
        "(MELEE/RANGED) or absurd moves like a devastating insult (SOCIAL). For each entry:\n"
        "- `category` and `success_stat` (the stat added to the d20 success roll; default by category).\n"
        "- `cost_type` ('mana' or 'stamina') and `cost`; keep costs affordable with the owner's pools.\n"
        "- `effects`: list of {target: 'target'|'self', stat, amount} with signed amounts such as '-2d6' "
        "(drain) or '+3' (boost). hp/mana/stamina change directly; strength/dexterity/intelligence/wisdom/"
        "charisma/armor_class changes last until the fight ends. Example insult: "
        "[{target:'target', stat:'charisma', amount:'-3'}, {target:'target', stat:'hp', amount:'-1d4'}].\n"
        "- `difficulty`: omit to roll against the target's armor class; set a number for a fixed DC.\n"
        "- Protagonist only: make 1-2 strong specials `is_locked: true` and unlock them through story "
        "progress with `unlock_required_item_id`, `unlock_required_scene_id`, "
        "`unlock_required_defeated_npc_id` and/or `unlock_guard_expression`, plus a short `unlock_text`. "
        "Only reference IDs that exist in this manifest.\n"
        "- Optional `on_success_text` / `on_failure_text` add flavour after the roll.\n"
        "Set `attack_mode: ATTACK_ON_SIGHT` only for NPCs that should attack the moment the protagonist "
        "enters their scene. Use an NPC `attack_trigger` (e.g. {required_item_id: 'ITEM_IDOL'}) for guards "
        "that turn hostile when the protagonist takes something, and `special_chance` (0-100, default 40) "
        "for how often an NPC uses its specials."
    )


def _build_cover_guidance(
    cover_source_manifest: Optional[dict[str, Any]],
    cover_source_adventure_name: Optional[str],
    cover_similarity_percent: int,
    allow_reuse_source_assets: bool,
    scripts_generation_enabled: bool = True,
) -> str:
    if not cover_source_manifest:
        return ""

    source_title = (
        cover_source_adventure_name
        or cover_source_manifest.get("title")
        or "Unknown Source Adventure"
    )
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
    source_scripts = [
        f"{s.get('id')} ({s.get('trigger')}: {s.get('name')})"
        for s in (cover_source_manifest.get("scripts") or [])
        if isinstance(s, dict) and s.get("id")
    ][:6]

    scripts_note = ""
    if scripts_generation_enabled:
        if source_scripts:
            scripts_note = (
                f"- The source adventure used event scripts: {', '.join(source_scripts)}. "
                "Since event scripting is ENABLED for this cover, you MUST adapt, reimagine, or match them with 1-3 new deterministic scripts in `scripts`.\n"
            )
        else:
            scripts_note = "- Event scripting is ENABLED for this cover! You MUST generate 1 to 3 creative deterministic event scripts in `scripts` matching this cover adventure.\n"

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
        f"{scripts_note}"
    )


def build_world_generation_prompts(
    *,
    title: str,
    original_prompt: str,
    language: Optional[str],
    selected_tone: Optional[str],
    automatic_npc_voice_assignment: bool,
    can_damage_npcs: bool,
    npcs_can_damage_protagonist: bool,
    quest_generation_enabled: bool,
    min_scenes: Optional[int],
    max_scenes: Optional[int],
    min_quests: Optional[int],
    max_quests: Optional[int],
    min_sequences: Optional[int] = None,
    max_sequences: Optional[int] = None,
    award_generation_enabled: bool,
    min_awards: Optional[int],
    max_awards: Optional[int],
    container_generation_enabled: bool,
    scripts_generation_enabled: bool = True,
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
    sequences: Optional[list[dict[str, Any]]] = None,
    generation_strictness: str = "creative",
) -> tuple[str, str]:
    """Build the system and user prompts for the world generation LLM call.

    Returns:
        A tuple of ``(system_prompt, user_prompt)``.
    """
    system_prompt = prompts.WORLD_GENERATION_SYSTEM_PROMPT
    if language:
        system_prompt += (
            f"\n\nCRITICAL: You MUST generate all content (names, descriptions, teaser, plot, "
            f"intro_text, walkthrough, quests) in {language}. Do not use any other language. "
            "Exception: `appearance` and `cover_appearance` keywords are always English."
        )
    if not quest_generation_enabled:
        system_prompt += (
            "\n\nQUEST GENERATION OVERRIDE: Do not generate any quests for this adventure."
        )

    scene_requirement = _build_scene_requirement(min_scenes, max_scenes)
    quest_requirement = _build_quest_requirement(quest_generation_enabled, min_quests, max_quests)
    award_requirement = _build_award_requirement(award_generation_enabled, min_awards, max_awards)
    cover_guidance = _build_cover_guidance(
        cover_source_manifest,
        cover_source_adventure_name,
        cover_similarity_percent,
        allow_reuse_source_assets,
        scripts_generation_enabled=scripts_generation_enabled,
    )

    user_prompt = prompts.WORLD_GENERATION_USER_PROMPT_TEMPLATE.format(
        title=title,
        original_prompt=original_prompt,
        selected_tone=selected_tone or "Standard RPG",
        scene_requirement=scene_requirement,
        can_damage_npcs="true" if can_damage_npcs else "false",
        npcs_can_damage_protagonist="true" if npcs_can_damage_protagonist else "false",
        voice_assignment_requirement=_build_voice_assignment_requirement(
            automatic_npc_voice_assignment
        ),
        cover_guidance=cover_guidance,
        quest_requirement=quest_requirement,
        award_requirement=award_requirement,
        text_log_requirement=_build_text_log_requirement(
            text_log_generation_enabled, min_text_logs, max_text_logs
        ),
    )
    user_prompt += _build_container_requirement(
        container_generation_enabled, min_containers, max_containers
    )
    user_prompt += _build_special_attack_requirement(can_damage_npcs, npcs_can_damage_protagonist)
    user_prompt += build_scripts_requirement(scripts_generation_enabled)
    user_prompt += _build_item_requirement(min_items, max_items)
    user_prompt += _build_switch_requirement(original_prompt)
    user_prompt += _build_sequences_requirement(
        sequences,
        generation_strictness,
        min_sequences,
        max_sequences,
    )

    return system_prompt, user_prompt
