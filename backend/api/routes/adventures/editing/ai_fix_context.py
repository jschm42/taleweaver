"""World summaries and prompt blocks for AI fix suggestions."""

import json
import logging
from typing import Any, Optional

from backend.api.routes.adventures.editing.ai_fix_scripts import (
    EXIT_SCRIPT_FIELDS,
    NPC_SCRIPT_FIELDS,
    OBJECT_SCRIPT_FIELDS,
    script_summary,
)
from backend.api.routes.adventures.editing.ai_fix_sequences import (
    focus_sequence,
    format_sequence_outline,
    summarize_sequences,
)
from backend.engine.world.scene_fields import SCENE_SCRIPT_FIELDS
from backend.schemas.validation import (
    AIFixSuggestionsRequest,
    FixProposal,
)

logger = logging.getLogger(__name__)


def _short_state(value: Any, *, limit: int = 400) -> str:
    text = "" if value is None else str(value)
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def _scene_summary(scene: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": scene.get("id"),
        "label": scene.get("label"),
        "description": _short_state(scene.get("description")),
        "decorative_objects": scene.get("decorative_objects") or [],
        "scripts": script_summary(scene, SCENE_SCRIPT_FIELDS),
    }


def _exit_summary(exit_row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": exit_row.get("id"),
        "from_scene_id": exit_row.get("from_scene_id"),
        "to_scene_id": exit_row.get("to_scene_id"),
        "label": exit_row.get("label"),
        "exit_type": exit_row.get("exit_type"),
        "is_locked": exit_row.get("is_locked"),
        "lock_description": _short_state(exit_row.get("lock_description"), limit=200),
        "code_to_unlock": exit_row.get("code_to_unlock"),
        "item_to_unlock": exit_row.get("item_to_unlock"),
        "rule_to_unlock": _short_state(exit_row.get("rule_to_unlock"), limit=200),
        "scripts": script_summary(exit_row, EXIT_SCRIPT_FIELDS),
    }


def _npc_summary(entity: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": entity.get("id"),
        "name": entity.get("name"),
        "description": _short_state(entity.get("description")),
        "current_scene_id": entity.get("current_scene_id"),
        "goal": _short_state(entity.get("goal")),
        "character": _short_state(entity.get("character")),
        "is_killable": entity.get("is_killable"),
        "stats": entity.get("stats") or {},
        "scripts": script_summary(entity, NPC_SCRIPT_FIELDS),
    }


def _object_summary(entity: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": entity.get("id"),
        "name": entity.get("name"),
        "description": _short_state(entity.get("description")),
        "current_scene_id": entity.get("current_scene_id"),
        "item_type": entity.get("item_type"),
        "is_portable": entity.get("is_portable"),
        "locked": entity.get("locked"),
        "code_to_unlock": entity.get("code_to_unlock"),
        "item_to_unlock": entity.get("item_to_unlock"),
        "rule_to_unlock": _short_state(entity.get("rule_to_unlock"), limit=200),
        "text_log_content": _short_state(entity.get("text_log_content"), limit=400),
        "text_log_format": entity.get("text_log_format"),
        "stats": entity.get("stats") or {},
        "scripts": script_summary(entity, OBJECT_SCRIPT_FIELDS),
    }


def _summarize_world_for_fix(payload: Any) -> dict[str, Any]:
    """Build a trimmed JSON-friendly snapshot of the world for the fix prompts."""

    def _adventure_dict() -> dict[str, Any]:
        adventure_raw = getattr(payload, "adventure", None) or {}
        if isinstance(adventure_raw, dict):
            return adventure_raw
        return {}

    adventure = _adventure_dict()
    adventure_payload: dict[str, Any] = {}
    for key in (
        "id",
        "title",
        "teaser",
        "plot",
        "rules",
        "intro_text",
        "tts_director_notes",
        "completed_condition",
        "gameover_condition",
        "completed_guard_expression",
        "gameover_guard_expression",
        "language",
        "selected_tone",
        "rule_enforcement_mode",
    ):
        value = adventure.get(key)
        if isinstance(value, str):
            adventure_payload[key] = _short_state(value, limit=1500)
        else:
            adventure_payload[key] = value

    scenes = [s for s in (getattr(payload, "scenes", None) or []) if isinstance(s, dict)]
    exits = [e for e in (getattr(payload, "exits", None) or []) if isinstance(e, dict)]
    npcs = [n for n in (getattr(payload, "npcs", None) or []) if isinstance(n, dict)]
    objects = [o for o in (getattr(payload, "objects", None) or []) if isinstance(o, dict)]

    raw_quests = adventure.get("quests") or []
    if not isinstance(raw_quests, list):
        raw_quests = []
    quests = []
    for q in raw_quests:
        if not isinstance(q, dict):
            continue
        quests.append(
            {
                "id": q.get("id"),
                "title": q.get("title"),
                "description": _short_state(q.get("description"), limit=400),
            }
        )

    return {
        "adventure": adventure_payload,
        "scenes": [_scene_summary(s) for s in scenes],
        "exits": [_exit_summary(e) for e in exits],
        "npcs": [_npc_summary(n) for n in npcs],
        "objects": [_object_summary(o) for o in objects],
        "quests": quests,
        "sequences": summarize_sequences(adventure.get("sequences")),
    }


def _signing(finding_or_payload: AIFixSuggestionsRequest) -> str:
    context_blob = json.dumps(
        finding_or_payload.finding_context or {},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return (
        f"{finding_or_payload.finding_severity}|{finding_or_payload.finding_code}"
        f"|{(finding_or_payload.finding_location or '').strip()}|{context_blob}"
    )


def _format_finding_context_block(payload: AIFixSuggestionsRequest) -> str:
    if not payload.finding_context:
        return ""
    try:
        formatted = json.dumps(payload.finding_context, ensure_ascii=False, indent=2)
    except TypeError:
        formatted = str(payload.finding_context)
    return f"- Context:\n```json\n{formatted}\n```"


def _format_proposal_patches_block(proposal: FixProposal) -> str:
    lines = []
    for i, patch in enumerate(proposal.patches or [], start=1):
        try:
            updates = json.dumps(patch.field_updates or {}, ensure_ascii=False, indent=2)
        except TypeError:
            updates = str(patch.field_updates)
        lines.append(
            f"Patch #{i}:\n"
            f"  target_type: {patch.target_type}\n"
            f"  target_id: {patch.target_id or ''}\n"
            f"  description: {patch.description}\n"
            f"  field_updates:\n{updates}"
        )
    return "\n\n".join(lines) if lines else "(no patches)"


def _format_world_context_block(summary: dict[str, Any]) -> str:
    """Return the shared adventure + world context block used by both AI fix prompts."""
    adventure = summary.get("adventure") or {}
    return (
        f"Adventure Title: {adventure.get('title', '')}\n"
        f"Language: {adventure.get('language', '')}\n"
        f"Rule Mode: {adventure.get('rule_enforcement_mode', 'rpg')}\n\n"
        f"=== STORY METADATA ===\n"
        f"Teaser: {adventure.get('teaser', '') or ''}\n"
        f"Plot: {adventure.get('plot', '') or ''}\n"
        f"Rules: {adventure.get('rules', '') or ''}\n"
        f"Intro Text: {adventure.get('intro_text', '') or ''}\n\n"
        f"=== SCENES ({len(summary.get('scenes') or [])}) ===\n"
        f"{json.dumps(summary.get('scenes') or [], ensure_ascii=False)}\n\n"
        f"=== EXITS ({len(summary.get('exits') or [])}) ===\n"
        f"{json.dumps(summary.get('exits') or [], ensure_ascii=False)}\n\n"
        f"=== NPCs ({len(summary.get('npcs') or [])}) ===\n"
        f"{json.dumps(summary.get('npcs') or [], ensure_ascii=False)}\n\n"
        f"=== OBJECTS ({len(summary.get('objects') or [])}) ===\n"
        f"{json.dumps(summary.get('objects') or [], ensure_ascii=False)}\n\n"
        f"=== QUESTS ({len(summary.get('quests') or [])}) ===\n"
        f"{json.dumps(summary.get('quests') or [], ensure_ascii=False)}\n\n"
        f"=== SEQUENCES (with walkthroughs) ===\n"
        f"{json.dumps(summary.get('sequences') or [], ensure_ascii=False)}\n"
    )


def _parse_finding_location(
    location: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    """Return ``(target_type, target_id)`` from a finding location like ``'object:SAFE_01'``."""
    if not location or not isinstance(location, str):
        return None, None
    parts = location.split(":", 1)
    if len(parts) != 2:
        return None, None
    ttype = parts[0].strip().lower()
    tid = parts[1].strip()
    if ttype not in {"scene", "object", "npc", "exit", "entity", "sequence"} or not tid:
        return None, None
    return ttype, tid


def _resolve_finding_target(
    summary: dict[str, Any], location: Optional[str]
) -> tuple[Optional[str], Optional[str]]:
    """Like ``_parse_finding_location`` but maps the validator's generic ``entity:<ID>``
    location to ``npc`` or ``object`` by looking the ID up in the summary."""
    target_type, target_id = _parse_finding_location(location)
    if target_type != "entity":
        return target_type, target_id
    if any(n.get("id") == target_id for n in summary.get("npcs") or []):
        return "npc", target_id
    if any(o.get("id") == target_id for o in summary.get("objects") or []):
        return "object", target_id
    return None, None


_Neighbors = list[tuple[str, Any]]
_MAX_NEIGHBORS = 12


def _upper_id(row: dict[str, Any], key: str) -> str:
    return str(row.get(key) or "").upper()


def _target_block(label: str, row: dict[str, Any]) -> str:
    return f"=== TARGET {label} ({row.get('id')}) ===\n{json.dumps(row, ensure_ascii=False)}\n"


def _focus_scene(summary: dict[str, Any], target_id: str) -> tuple[str, _Neighbors]:
    scene = next((s for s in summary.get("scenes") or [] if s.get("id") == target_id), None)
    if not scene:
        return "", []
    sid = _upper_id(scene, "id")
    neighbors: _Neighbors = [
        ("object", o)
        for o in summary.get("objects") or []
        if _upper_id(o, "current_scene_id") == sid
    ]
    neighbors += [
        ("npc", n) for n in summary.get("npcs") or [] if _upper_id(n, "current_scene_id") == sid
    ]
    neighbors += [
        ("exit", ex)
        for ex in summary.get("exits") or []
        if sid in (_upper_id(ex, "from_scene_id"), _upper_id(ex, "to_scene_id"))
    ]
    return _target_block("SCENE", scene), neighbors


def _focus_entity(
    summary: dict[str, Any], target_type: str, target_id: str
) -> tuple[str, _Neighbors]:
    entities = summary.get("objects" if target_type == "object" else "npcs") or []
    entity = next((e for e in entities if e.get("id") == target_id), None)
    if not entity:
        return "", []
    scene_id = _upper_id(entity, "current_scene_id")
    scene = next(
        (s for s in summary.get("scenes") or [] if scene_id and _upper_id(s, "id") == scene_id),
        None,
    )
    return _target_block(target_type.upper(), entity), [("scene", scene)] if scene else []


def _focus_exit(summary: dict[str, Any], target_id: str) -> tuple[str, _Neighbors]:
    ex = next((e for e in summary.get("exits") or [] if e.get("id") == target_id), None)
    if not ex:
        return "", []
    ends = (_upper_id(ex, "from_scene_id"), _upper_id(ex, "to_scene_id"))
    neighbors = [("scene", s) for s in summary.get("scenes") or [] if _upper_id(s, "id") in ends]
    return _target_block("EXIT", ex), neighbors


def _focus_target(
    summary: dict[str, Any], target_type: Optional[str], target_id: Optional[str]
) -> tuple[str, _Neighbors]:
    if target_type == "scene":
        return _focus_scene(summary, target_id or "")
    if target_type in ("object", "npc"):
        return _focus_entity(summary, target_type, target_id or "")
    if target_type == "exit":
        return _focus_exit(summary, target_id or "")
    if target_type == "sequence":
        return focus_sequence(summary, target_id or "")
    return "", []


def _format_neighbors(neighbors: _Neighbors) -> str:
    grouped: dict[str, list[Any]] = {}
    for kind, ent in neighbors[:_MAX_NEIGHBORS]:
        grouped.setdefault(kind, []).append(ent)
    chunks = [
        f"--- {kind.upper()} ({len(ents)}) ---\n{json.dumps(ents, ensure_ascii=False)}"
        for kind, ents in grouped.items()
    ]
    return "\n\n".join(chunks) + "\n" if chunks else ""


def _format_focused_world_block(
    summary: dict[str, Any],
    *,
    location: Optional[str],
) -> str:
    """Build a small world context focused on the targeted finding.

    Drops full entity lists and instead ships only the targeted entity plus a
    few neighbors. For large adventures this turns a multi-thousand-token
    prompt into a few hundred tokens, which is the difference between an
    instant response and a provider timeout.
    """
    adventure = summary.get("adventure") or {}
    target_block, neighbors = _focus_target(summary, *_resolve_finding_target(summary, location))
    neighbor_block = _format_neighbors(neighbors)
    return (
        f"Adventure Title: {adventure.get('title', '')}\n"
        f"Language: {adventure.get('language', '')}\n"
        f"Rule Mode: {adventure.get('rule_enforcement_mode', 'rpg')}\n\n"
        f"=== STORY METADATA ===\n"
        f"Plot: {_short_state(adventure.get('plot') or '', limit=600)}\n"
        f"Rules: {_short_state(adventure.get('rules') or '', limit=400)}\n"
        f"Sequences (outline, in chapter order): {format_sequence_outline(summary)}\n\n"
        f"{target_block}\n"
        f"=== ADJACENT ENTITIES ===\n"
        f"{neighbor_block or '(none)'}\n"
    )
