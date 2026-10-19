"""Pure helpers for building the per-turn LLM context (see turn_llm_pipeline)."""

from __future__ import annotations

from typing import Any

from backend.models.world_entity import WorldEntity, WorldExit

# Session override key -> WorldEntity attribute it replaces for this turn.
ENTITY_OVERRIDE_ATTRIBUTES: dict[str, str] = {
    "hp": "hp",
    "mana": "mana",
    "stamina": "stamina",
    "spatial_position": "spatial_position",
    "name": "name",
    "description": "description",
    "current_scene_id": "current_scene_id",
    "is_in_inventory": "is_in_inventory",
    "inventory": "inventory",
    "switch_state": "current_switch_state",
    # Transient (non-mapped) attribute read by the location prompt context.
    "locked": "session_locked_override",
    "notes": "notes",
    "moveable": "moveable",
    "allowed_scenes": "allowed_scenes",
}

_STRICTNESS_PREFIXES = {
    "strict": "[STRICT ADHERENCE REQUIRED] You MUST strictly follow this walkthrough. Do not allow the player to bypass these steps.\n\n",
    "creative": "[CREATIVE FOUNDATION] Use this walkthrough as a creative foundation. Allow the player to find alternative solutions.\n\n",
}

_SEQUENCE_HARD_REQUIREMENTS = (
    ("required_item_id", "obtain item '{}'"),
    ("required_scene_id", "enter scene '{}'"),
    ("required_defeated_npc_id", "defeat NPC '{}'"),
)

TECHNICAL_TURN_INSTRUCTION = (
    "\nIMPORTANT: The player just synchronized their character sheet or world state (e.g., closing a menu). "
    "This is a TECHNICAL turn. Respond only if something meaningful changed (e.g., equipment effects). "
    "Do NOT list available actions, do NOT provide suggestions, and do NOT use meta-formatting like '---' or 'You can:'. "
    "Keep the narrative flow natural if you speak at all.\n"
)


def apply_entity_overrides(entities: list[WorldEntity], overrides: dict[str, Any]) -> None:
    """Applies session-state overrides onto the (session-scoped) entities for this turn."""
    for ent in entities:
        override = overrides.get(ent.id)
        if override is None:
            continue
        for key, attribute in ENTITY_OVERRIDE_ATTRIBUTES.items():
            if key in override:
                setattr(ent, attribute, override[key])
        if "is_hidden" in override:
            ent.is_hidden = override["is_hidden"]
        elif str(ent.item_type or "").upper() == "CONSTRUCTABLE":
            ent.is_hidden = True
        ent.is_defeated = bool(override.get("is_defeated", False))


def orient_exits(db_exits: list[WorldExit], current_scene_id: str) -> list[WorldExit]:
    """Returns exits leading out of the current scene; bidirectional exits are mirrored."""
    exits: list[WorldExit] = []
    for exit_row in db_exits:
        if exit_row.from_scene_id == current_scene_id:
            exits.append(exit_row)
            continue
        exits.append(
            WorldExit(
                id=exit_row.id,
                template_id=exit_row.template_id,
                session_id=exit_row.session_id,
                from_scene_id=exit_row.to_scene_id,
                to_scene_id=exit_row.from_scene_id,
                label=exit_row.label,
                exit_type=exit_row.exit_type,
                is_locked=exit_row.is_locked,
                lock_description=exit_row.lock_description,
                code_to_unlock=exit_row.code_to_unlock,
                item_to_unlock=exit_row.item_to_unlock,
                rule_to_unlock=exit_row.rule_to_unlock,
            )
        )
    return exits


def _find_active_sequence(adventure: Any, state: Any) -> dict | None:
    sequences = getattr(adventure, "sequences", None) or []
    ordered = sorted(sequences, key=lambda seq: seq.get("order", 1))
    for index, seq in enumerate(ordered):
        is_first_default = not state.active_sequence_id and index == 0
        if seq.get("id") == state.active_sequence_id or is_first_default:
            return seq
    return None


def _sequence_end_condition(seq: dict) -> str:
    end_condition = seq.get("end_condition", "")
    hard_reqs = [
        template.format(seq[key]) for key, template in _SEQUENCE_HARD_REQUIREMENTS if seq.get(key)
    ]
    if not hard_reqs:
        return end_condition
    req_str = " AND ".join(hard_reqs)
    if end_condition:
        return f"{end_condition} (Deterministic triggers required: {req_str})"
    return f"Deterministic triggers required: {req_str}"


def resolve_sequence_guidance(adventure: Any, state: Any) -> tuple[str, str]:
    """Returns (walkthrough, end_condition) for the active sequence (chapter)."""
    walkthrough = ""
    end_condition = state.completed_condition or adventure.completed_condition
    active_seq = _find_active_sequence(adventure, state)
    if active_seq is not None:
        walkthrough = active_seq.get("walkthrough", "")
        end_condition = _sequence_end_condition(active_seq)

    walkthrough = walkthrough or state.walkthrough or adventure.walkthrough
    prefix = _STRICTNESS_PREFIXES.get(getattr(adventure, "generation_strictness", None) or "")
    if walkthrough and prefix:
        walkthrough = f"{prefix}{walkthrough}"
    return walkthrough, end_condition


def resolve_model_settings(llm_settings: dict[str, Any]) -> dict[str, Any]:
    """Resolves providers/models for the small, complex, and compression categories."""
    get = llm_settings.get
    return {
        "small_model_provider": get("small_model_provider")
        or get("complex_model_provider")
        or get("preferred_provider")
        or "openai",
        "complex_model_provider": get("complex_model_provider")
        or get("small_model_provider")
        or get("preferred_provider")
        or "openai",
        "small_model": get("small_model") or "gpt-4o-mini",
        "complex_model": get("complex_model") or "gpt-4o",
        "compression_model_provider": get("compression_model_provider")
        or get("small_model_provider")
        or "openai",
        "compression_model": get("compression_model") or get("small_model") or "gpt-4o-mini",
        "compression_max_tokens": int(get("compression_max_tokens") or 4096),
    }


def bable_fish_instruction(language: str) -> str:
    """Translation protocol appended to the narration system prompt."""
    return (
        "\n\n--- BABLE FISH TRANSLATION PROTOCOL ---\n"
        f"TARGET LANGUAGE: {language.upper()}\n"
        f"INSTRUCTION: You MUST translate ALL your output (narration, dialogue, descriptions) into {language}. "
        "Do NOT respond in English or the original world language if it differs. "
        "Note: The chat history may contain messages in various languages due to previous Bable Fish settings. "
        f"IGNORE those languages and strictly use {language} for the current turn. "
        f"The player has activated their Bable Fish, so everything they hear/see must be in {language}."
        "\n----------------------------------------\n"
    )
