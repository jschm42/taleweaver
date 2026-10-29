"""Prompt context blocks describing the current location, hidden entities, and off-scene NPCs.

Two detail levels exist:
- "concise": used by the mechanics pass (Pass 1). Includes lock requirements so the
  small model can emit unlock events.
- "full": used by the narration pass (Pass 2). Includes rich descriptions but never
  lock secrets (codes, key items, unlock rules) — unlocks are resolved by Pass 1 and the
  guardrails, so the narrator neither needs nor should be able to leak them.
"""

from typing import Any, Optional

from backend.engine.switch_states import state_label


def _format_item_refs(items: Optional[list]) -> list[str]:
    refs: list[str] = []
    for item in items or []:
        if isinstance(item, str):
            refs.append(item)
            continue
        if not isinstance(item, dict):
            continue
        item_name = item.get("name")
        item_id = item.get("id")
        if item_name and item_id:
            refs.append(f"{item_name} (ID: {item_id})")
        elif item_name:
            refs.append(item_name)
    return refs


def _movement_label(entity: Any, separator: str) -> str:
    is_moveable = bool(
        getattr(entity, "moveable", False)
        or str(getattr(entity, "movement_type", "") or "").upper() == "MOVABLE"
    )
    allowed = getattr(entity, "allowed_scenes", None) or []
    if is_moveable and allowed:
        return f"{separator}Movable: Allowed in {', '.join(allowed)}"
    if is_moveable:
        return f"{separator}Movable: Any scene"
    return f"{separator}Stationary"


def _describe_npc(e: Any, detail: str) -> str:
    stats = []
    if e.hp is not None:
        stats.append(f"HP:{e.hp}/{e.max_hp or e.hp}")
    if e.mana is not None:
        stats.append(f"Mana:{e.mana}/{e.max_mana or e.mana}")
    if e.stamina is not None:
        stats.append(f"Stamina:{e.stamina}/{e.max_stamina or e.stamina}")

    stat_str = f" [{' '.join(stats)}]" if stats else ""
    pos_str = f" (Position: {e.spatial_position})" if e.spatial_position else ""
    goal_str = f" [Goal: {e.goal}]" if e.goal else ""
    char_str = f" [Character: {e.character}]" if e.character else ""
    looks = getattr(e, "appearance", None)
    looks_str = f" [Looks: {looks}]" if looks else ""
    hidden_str = " [HIDDEN]" if getattr(e, "is_hidden", False) else ""
    inv_refs = _format_item_refs(e.inventory)
    inv_str = f" [Inventory: {', '.join(inv_refs)}]" if inv_refs else ""
    defeated_str = " [DEFEATED]" if getattr(e, "is_defeated", False) else ""
    desc_str = f" - Description: {e.description}" if (e.description and detail != "concise") else ""
    notes_str = f' [Status/Notes: "{e.notes}"]' if getattr(e, "notes", None) else ""
    move_str = f" [{_movement_label(e, '').strip()}]"
    return (
        f"{e.name} (ID: {e.id}){stat_str}{pos_str}{goal_str}{char_str}{looks_str}{hidden_str}"
        f"{defeated_str}{notes_str}{move_str}{inv_str}{desc_str}"
    )


def _state_with_label(switch_cfg: dict[str, Any], state: Any) -> str:
    label = state_label(switch_cfg, state)
    state_id = str(state or "").strip().upper()
    return state_id if label == state_id else f'{state_id} "{label}"'


def _switch_details(e: Any, detail: str) -> str:
    metadata = e.metadata_json or {}
    switch_cfg = metadata.get("switch") or {}
    states = metadata.get("switch_states") or switch_cfg.get("states") or []
    # The GM sees the ID (used by mechanics) and the label the player reads.
    shown = [_state_with_label(switch_cfg, s) for s in states]
    states_str = f" (Possible states: {', '.join(shown)})" if states else ""

    current_st = getattr(e, "current_switch_state", None)
    if not current_st:
        current_st = switch_cfg.get("initial_state") or metadata.get("switch_initial_state") or ""
    current_str = (
        f" [Current State: {_state_with_label(switch_cfg, current_st)}]" if current_st else ""
    )

    if detail != "concise":
        return f"{states_str}{current_str}"

    # Per-transition gate summary so the mechanics model knows the requirements.
    transitions = metadata.get("switch_transitions") or switch_cfg.get("transitions") or []
    gate_parts: list[str] = []
    for t in transitions if isinstance(transitions, list) else []:
        if not isinstance(t, dict):
            continue
        to_s = str(t.get("to") or t.get("to_state") or "").strip()
        gates = t.get("gates") if isinstance(t.get("gates"), dict) else {}
        reqs = [
            f"{label}:{value}"
            for label, value in (
                ("code", str(gates.get("code") or t.get("code") or "").strip()),
                ("item", str(gates.get("item") or t.get("required_item") or "").strip()),
                ("rule", str(gates.get("rule") or t.get("required_rule") or "").strip()),
            )
            if value
        ]
        if to_s and reqs:
            gate_parts.append(f"→{to_s}({','.join(reqs)})")
    gate_str = f" [Gates: {' '.join(gate_parts)}]" if gate_parts else ""
    return f"{states_str}{current_str}{gate_str}"


def _container_details(e: Any, detail: str) -> str:
    # Lock info lives in metadata_json; the session override (if any) wins.
    meta = dict(e.metadata_json or {})
    requirements = [
        (key, str(meta.get(key) or "").strip())
        for key in ("code_to_unlock", "item_to_unlock", "rule_to_unlock")
    ]
    requirements = [(key, value) for key, value in requirements if value]
    session_locked = getattr(e, "session_locked_override", None)
    is_locked = session_locked if isinstance(session_locked, bool) else bool(requirements)

    if not is_locked:
        lock_str = " [UNLOCKED]"
    elif detail == "concise":
        lock_str = f" [{', '.join(['LOCKED'] + [f'{key}:{value}' for key, value in requirements])}]"
    else:
        lock_str = " [LOCKED]"

    cont_items = _format_item_refs(e.inventory)
    cont_str = f" [Contains: {', '.join(cont_items)}]" if cont_items else " [Empty]"
    return f"{lock_str}{cont_str}"


def _describe_object(e: Any, detail: str) -> str:
    pos_str = f" (Position: {e.spatial_position})" if e.spatial_position else ""
    hidden_str = " [HIDDEN]" if getattr(e, "is_hidden", False) else ""
    item_type = str(e.item_type or "DEFAULT").upper()
    type_str = f" [Type: {item_type}]"

    extra = ""
    if item_type == "SWITCH":
        extra = _switch_details(e, detail)
    elif item_type == "CONTAINER":
        extra = _container_details(e, detail)
    elif item_type == "READABLE":
        metadata = e.metadata_json or {}
        fmt = metadata.get("text_log_format") or getattr(e, "text_log_format", "DOCUMENT")
        content = metadata.get("text_log_content") or ""
        extra = f' [Format: {fmt}] [Readable text content: "{content}"]'

    if detail == "concise":
        return f"{e.name} (ID: {e.id}){type_str}{pos_str}{hidden_str}{extra}"
    desc_str = f" - Description: {e.description}" if e.description else ""
    return f"- {e.name} (ID: {e.id}):{type_str}{desc_str}{pos_str}{hidden_str}{extra}"


def _describe_exits(exits: list, detail: str) -> str:
    if detail == "concise":
        exit_list = []
        for e in exits:
            status = "[LOCKED]" if e.is_locked else "[OPEN]"
            status_parts = []
            if e.is_locked:
                if getattr(e, "code_to_unlock", None):
                    status_parts.append(f"code:{e.code_to_unlock}")
                if getattr(e, "item_to_unlock", None):
                    status_parts.append(f"item:{e.item_to_unlock}")
                if getattr(e, "rule_to_unlock", None):
                    status_parts.append(f"rule:{e.rule_to_unlock}")
            status_req = f"({','.join(status_parts)})" if status_parts else ""
            exit_list.append(f"{e.label}->{e.to_scene_id}{status}{status_req}")
        return "EXITS: " + "; ".join(exit_list) + "\n"

    exit_list = []
    for e in exits:
        status = "[LOCKED]" if e.is_locked else "[OPEN]"
        lock_desc = f" ({e.lock_description})" if (e.is_locked and e.lock_description) else ""
        exit_list.append(f"- {e.label} to {e.to_scene_id} {status}{lock_desc}")
    return "AVAILABLE EXITS:\n" + "\n".join(exit_list) + "\n"


def build_location_context(
    current_scene=None, entities=None, exits=None, detail_level: str = "full"
) -> str:
    if not current_scene:
        return ""

    detail = detail_level if detail_level in {"full", "concise"} else "full"
    description = current_scene.description or ""
    decorative_list = current_scene.decorative_objects or []
    decor_items = ""
    if isinstance(decorative_list, list):
        decor_items = ", ".join(str(d).strip() for d in decorative_list if str(d).strip())
    decorative_suffix = (
        f"DECORATIVE BACKGROUND DETAILS (STATIC, NON-INTERACTABLE): {decor_items}\n"
        if decor_items
        else ""
    )

    if detail == "concise":
        short_desc = description.strip().replace("\n", " ")
        if len(short_desc) > 240:
            short_desc = short_desc[:240].rstrip() + "..."
        location_context = (
            f"\nCURRENT LOCATION: {current_scene.label} (ID: {current_scene.id})\n"
            f"SCENE SUMMARY: {short_desc}\n"
        )
    else:
        location_context = (
            f"\nCURRENT LOCATION:\n"
            f"NAME: {current_scene.label} (ID: {current_scene.id})\n"
            f"DESCRIPTION: {description}\n"
        )
    location_context += decorative_suffix

    npcs = [_describe_npc(e, detail) for e in entities or [] if e.entity_type == "NPC"]
    objects = [_describe_object(e, detail) for e in entities or [] if e.entity_type == "OBJECT"]

    if npcs and detail == "concise":
        location_context += f"NPCS: {', '.join(npcs)}\n"
    elif npcs:
        location_context += "PRESENT NPCs:\n" + "\n".join(f"- {npc}" for npc in npcs) + "\n"
    if objects and detail == "concise":
        location_context += f"OBJECTS: {', '.join(objects)}\n"
    elif objects:
        location_context += "INTERACTABLE OBJECTS:\n" + "\n".join(objects) + "\n"

    if exits:
        location_context += _describe_exits(exits, detail)
    return location_context


def build_hidden_entities_context(
    hidden_entities: Optional[list] = None, for_narration: bool = False
) -> str:
    """GM-only block for hidden NPCs/objects in the current scene with their reveal rules."""
    if not hidden_entities:
        return ""

    lines = [
        "HIDDEN ENTITIES IN CURRENT SCENE (GM EYES ONLY — Do NOT reveal their existence to the player unless the reveal condition is met):"
    ]
    for e in hidden_entities:
        pos_str = f" (Position: {e.spatial_position})" if e.spatial_position else ""
        reveal_rule = getattr(e, "reveal_rule", None) or ""
        entity_type = getattr(e, "entity_type", "ENTITY")
        if reveal_rule:
            rule_str = f' | Reveal condition: "{reveal_rule}"'
        elif entity_type == "NPC":
            rule_str = " | Reveal condition: (default) reveal when the protagonist searches the scene OR when this NPC starts speaking"
        else:
            rule_str = (
                " | Reveal condition: (default) reveal when the protagonist searches the scene"
            )
        lines.append(f"- [{entity_type}] ID='{e.id}' Name='{e.name}'{pos_str}{rule_str}")

    if for_narration:
        lines.append(
            "Only describe a hidden entity when the player's action in this turn meets its reveal condition."
        )
    else:
        lines.append(
            'REVEAL MECHANIC: When a reveal condition is met, reveal the entity by including its exact ID in \'updated_entities\' with is_hidden=false (e.g. {"entity_id": "ITEM_ID", "is_hidden": false}) or in \'spawned_items\'. '
            "This immediately makes the item/NPC visible to the player."
        )
    return "\n".join(lines) + "\n"


def build_world_npcs_context(
    other_npcs: Optional[list] = None, scene_map: Optional[dict[str, str]] = None
) -> str:
    if not other_npcs:
        return ""

    lines = [
        "WORLD NPCS (INTERNAL GM META-INFORMATION - Do NOT reveal these locations or existence to the player unless justified):"
    ]
    for npc in other_npcs:
        scene_label = (
            scene_map.get(npc.current_scene_id, npc.current_scene_id)
            if scene_map
            else npc.current_scene_id
        )
        pos_str = f", Position: {npc.spatial_position}" if npc.spatial_position else ""
        hidden_str = " [HIDDEN]" if getattr(npc, "is_hidden", False) else ""
        desc = (npc.description or "").strip()
        if desc.endswith("."):
            desc = desc[:-1]
        goal_str = f", Goal: {npc.goal}" if npc.goal else ""
        char_str = f", Character: {npc.character}" if npc.character else ""
        looks = getattr(npc, "appearance", None)
        looks_str = f", Looks: {looks}" if looks else ""
        inv_refs = _format_item_refs(npc.inventory)
        inv_str = f", Inventory: {', '.join(inv_refs)}" if inv_refs else ""
        notes_str = f', Status: "{npc.notes}"' if getattr(npc, "notes", None) else ""
        move_str = _movement_label(npc, ", ")
        lines.append(
            f"- {npc.name}: {desc}. Location: {scene_label}{pos_str}{goal_str}{char_str}{looks_str}"
            f"{hidden_str}{notes_str}{move_str}{inv_str}"
        )

    return "\n".join(lines) + "\n"
