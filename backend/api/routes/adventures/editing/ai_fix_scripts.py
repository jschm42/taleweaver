"""Script, text and guard fields of AI fix / World-Builder patches.

Lists the inline trigger fields each patch target accepts, checks their syntax with the
script sandbox before a proposal reaches the author, stores them where the editor does,
and summarizes existing scripts so the LLM can reuse their flags and variables.
"""

from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm.attributes import flag_modified

from backend.engine.scripting.sandbox import SafeAstInterpreter
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene

_SUMMARY_SCRIPT_LIMIT = 300


def _hooks(*bases: str) -> tuple[str, ...]:
    return tuple(f"{base}_{kind}" for base in bases for kind in ("script", "text"))


EXIT_SCRIPT_FIELDS = (
    "unlock_expression",
    *_hooks("on_open_exit", "on_exit_used", "on_unlock_success", "on_unlock_failure"),
)
NPC_SCRIPT_FIELDS = _hooks("on_defeat", "on_protagonist_enters_scene", "on_interact")
ITEM_EVENT_FIELDS = _hooks("on_pickup", "on_drop", "on_equip", "on_unequip", "on_interact")
OBJECT_SCRIPT_FIELDS = (
    "unlock_expression",
    *_hooks("on_unlock_success", "on_unlock_failure", "on_items_added", "on_read"),
    "craft_guard_expression",
    *_hooks("on_craft_success", "on_craft_failure"),
    *ITEM_EVENT_FIELDS,
)
PROTAGONIST_SCRIPT_FIELDS = _hooks("on_hp_change", "on_status_change")
SEQUENCE_SCRIPT_FIELDS = (*_hooks("on_start_sequence", "on_end_sequence"), "helpers_script")

# Fields whose value is sandboxed ``tw`` code (exec) or a boolean guard expression (eval).
_SOFT_RULE_SCRIPT_SUFFIX = ".script"
_SOFT_RULE_GUARD_SUFFIX = ".guard_expression"


def _is_guard_field(field: str) -> bool:
    return field.endswith("_expression")


def _is_code_field(field: str) -> bool:
    return field.endswith(("_script", _SOFT_RULE_SCRIPT_SUFFIX))


def _syntax_errors(field: str, value: Any) -> list[str]:
    code = str(value or "").strip()
    if not code:
        return []
    if _is_guard_field(field):
        return SafeAstInterpreter.check_expression_syntax(code)
    if _is_code_field(field):
        return SafeAstInterpreter.check_syntax(code)
    return []


def script_violations(target_type: str, field_updates: dict[str, Any]) -> list[str]:
    """Readable syntax problems of every script / guard value in ``field_updates``."""
    violations: list[str] = []
    for field, value in field_updates.items():
        errors = _syntax_errors(str(field), value)
        if errors:
            violations.append(f"{target_type}.{field} has invalid syntax ({errors[0]})")
    return violations


def ensure_valid_scripts(target_type: str, field_updates: dict[str, Any]) -> None:
    """Reject a patch whose script or guard would fail in the sandbox."""
    violations = script_violations(target_type, field_updates)
    if violations:
        raise HTTPException(status_code=400, detail=violations[0])


def _clean(value: Any) -> Any:
    return str(value or "").strip() or None


def set_columns(row: WorldScene | WorldExit, fields: tuple[str, ...], updates: dict) -> None:
    """Store script/text fields that are real columns (scenes and exits)."""
    for field in (f for f in fields if f in updates):
        setattr(row, field, _clean(updates[field]))


def set_metadata(ent: WorldEntity, fields: tuple[str, ...], updates: dict[str, Any]) -> None:
    """Store script/text fields in ``metadata_json`` like the editor does (NPCs and objects)."""
    sent = [f for f in fields if f in updates]
    if not sent:
        return
    metadata_json = dict(ent.metadata_json or {})
    for field in sent:
        metadata_json[field] = _clean(updates[field])
    ent.metadata_json = metadata_json
    flag_modified(ent, "metadata_json")


def script_summary(row: dict[str, Any], fields: tuple[str, ...]) -> dict[str, str]:
    """Non-empty script/text/guard fields of a payload row (flat or in ``metadata_json``)."""
    metadata_json = row.get("metadata_json")
    metadata_json = metadata_json if isinstance(metadata_json, dict) else {}
    summary: dict[str, str] = {}
    for field in fields:
        value = str(row.get(field) or metadata_json.get(field) or "").strip()
        if value:
            summary[field] = value[:_SUMMARY_SCRIPT_LIMIT]
    return summary
