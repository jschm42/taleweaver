"""Applies AI fix proposal patches to the adventure template."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.editing.ai_fix_targets import (
    _allowed_fields_for,
    _normalize_field_value,
    _resolve_entity_target,
    _resolve_exit_target,
    _resolve_scene_target,
)
from backend.api.routes.adventures.editing.common import (
    _ensure_template_scene_exists,
    _get_template_avatar,
    _normalize_lock_fields,
    _restore_missing_template_avatar,
)
from backend.models.adventure_template import AdventureTemplate
from backend.models.world_entity import WorldEntity, WorldExit
from backend.schemas.validation import FixProposalEntityPatch

logger = logging.getLogger(__name__)

_LOCK_FIELDS = ("code_to_unlock", "item_to_unlock", "rule_to_unlock")
_VITALS = {"hp": "max_hp", "mana": "max_mana", "stamina": "max_stamina"}
_TEXT_LOG_FORMATS = {"DOCUMENT", "SCROLL", "BOOK", "SIGN"}
_MAX_DECORATIVE_OBJECTS = 7


def _clean_updates(target_type: str, field_updates: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Keep only allowlisted, non-empty field updates for the target type."""
    allowed = _allowed_fields_for(target_type)
    return {
        field: value
        for field, value in (field_updates or {}).items()
        if field in allowed
        and value is not None
        and not (isinstance(value, str) and not value.strip())
    }


def _unresolved(kind: str, raw_target_id: str) -> HTTPException:
    # ``ai_fix_apply`` treats "could not be resolved" as a stale cached proposal.
    return HTTPException(
        status_code=400,
        detail=(
            f"{kind} '{raw_target_id}' could not be resolved in this adventure. "
            "The AI reference is stale; please retry."
        ),
    )


def _merged_lock(updates: dict[str, Any], current: dict[str, Any]) -> tuple[str, str, str]:
    """Normalized (code, item, rule) with patch values taking precedence over ``current``."""
    return _normalize_lock_fields(
        code_to_unlock=str(updates.get("code_to_unlock", current.get("code_to_unlock") or "")),
        item_to_unlock=str(updates.get("item_to_unlock", current.get("item_to_unlock") or "")),
        rule_to_unlock=str(updates.get("rule_to_unlock", current.get("rule_to_unlock") or "")),
    )


async def _patch_adventure(adv: AdventureTemplate, updates: dict[str, Any]) -> None:
    for field, value in updates.items():
        setattr(adv, field, _normalize_field_value(value))


async def _patch_protagonist(
    db: AsyncSession, template_id: str, adv: AdventureTemplate, updates: dict[str, Any]
) -> None:
    avatar = await _get_template_avatar(db, template_id)
    if not avatar:
        avatar = await _restore_missing_template_avatar(db, template_id, adv)
    if not avatar:
        raise HTTPException(status_code=400, detail="Protagonist not found for AI fix")
    for field, value in updates.items():
        if field in _VITALS:
            setattr(avatar, field, int(value))
            setattr(avatar, _VITALS[field], int(value))
            continue
        setattr(avatar, field, _normalize_field_value(value))


def _decorative_objects(values: Any) -> Optional[list[str]]:
    decor: list[str] = []
    for d in values or []:
        s = str(d).strip()
        if len(s) > 100:
            raise HTTPException(
                status_code=400, detail="decorative_objects entries must be <= 100 chars"
            )
        if s:
            decor.append(s)
    return decor[:_MAX_DECORATIVE_OBJECTS] or None


async def _patch_scene(
    db: AsyncSession, template_id: str, raw_target_id: str, updates: dict[str, Any]
) -> str:
    scene = await _resolve_scene_target(db=db, template_id=template_id, raw_target_id=raw_target_id)
    if scene is None:
        raise _unresolved("scene", raw_target_id)
    if "label" in updates:
        scene.label = str(updates["label"]).strip()[:120]
    if "description" in updates:
        scene.description = str(updates["description"]).strip()
    if "decorative_objects" in updates:
        scene.decorative_objects = _decorative_objects(updates["decorative_objects"])
        flag_modified(scene, "decorative_objects")
    return f"scene:{scene.id}"


def _patch_exit_lock(world_exit: WorldExit, updates: dict[str, Any]) -> None:
    current = {f: getattr(world_exit, f) for f in _LOCK_FIELDS}
    code, item, rule = _merged_lock(updates, current)
    if (code or item or rule) and not str(world_exit.lock_description or "").strip():
        raise HTTPException(
            status_code=400,
            detail="A lock description is required when a code, item, or rule gate is configured on an exit.",
        )
    world_exit.code_to_unlock = code or None
    world_exit.item_to_unlock = item or None
    world_exit.rule_to_unlock = rule or None
    if "locked" not in updates:
        world_exit.is_locked = bool(code or item or rule)


async def _patch_exit(
    db: AsyncSession, template_id: str, raw_target_id: str, updates: dict[str, Any]
) -> str:
    world_exit = await _resolve_exit_target(
        db=db, template_id=template_id, raw_target_id=raw_target_id
    )
    if world_exit is None:
        raise _unresolved("exit", raw_target_id)
    if "label" in updates:
        world_exit.label = str(updates["label"]).strip()[:120]
    if "lock_description" in updates:
        world_exit.lock_description = str(updates["lock_description"]).strip() or None
    if "exit_type" in updates:
        world_exit.exit_type = str(updates["exit_type"]).strip().lower()
    if "locked" in updates:
        world_exit.is_locked = bool(updates["locked"])
    if any(k in updates for k in _LOCK_FIELDS):
        _patch_exit_lock(world_exit, updates)
    return f"exit:{world_exit.id}"


def _patch_npc_fields(ent: WorldEntity, updates: dict[str, Any]) -> None:
    if "goal" in updates:
        ent.goal = str(updates["goal"]).strip() or None
    if "character" in updates:
        ent.character = str(updates["character"]).strip() or None
    if "is_killable" in updates:
        ent.is_killable = bool(updates["is_killable"])
    if "moveable" in updates:
        ent.moveable = bool(updates["moveable"])
        ent.movement_type = "MOVABLE" if ent.moveable else "STATIONARY"
    if "allowed_scenes" in updates:
        ent.allowed_scenes = list(updates["allowed_scenes"] or [])
    if "notes" in updates:
        ent.notes = str(updates["notes"]).strip() or None


def _patch_container_lock(
    metadata_json: dict[str, Any], updates: dict[str, Any], is_container: bool
) -> None:
    if not any(k in updates for k in ("locked", *_LOCK_FIELDS)):
        return
    if not is_container:
        for key in (*_LOCK_FIELDS, "locked"):
            metadata_json.pop(key, None)
        return
    code, item, rule = _merged_lock(updates, metadata_json)
    metadata_json.update(code_to_unlock=code, item_to_unlock=item, rule_to_unlock=rule)
    metadata_json["locked"] = bool(updates.get("locked", code or item or rule))


def _patch_text_log(metadata_json: dict[str, Any], updates: dict[str, Any]) -> None:
    if "text_log_content" in updates:
        text = str(updates["text_log_content"]).strip()
        if len(text) > 1000:
            raise HTTPException(status_code=400, detail="text_log_content must be <= 1000 chars")
        metadata_json["text_log_content"] = text
    if "text_log_format" in updates:
        fmt = str(updates["text_log_format"]).strip().upper()
        if fmt not in _TEXT_LOG_FORMATS:
            raise HTTPException(status_code=400, detail="text_log_format invalid")
        metadata_json["text_log_format"] = fmt


def _patch_object_fields(ent: WorldEntity, updates: dict[str, Any]) -> None:
    item_type = str(ent.item_type or "").upper()
    metadata_json = dict(ent.metadata_json or {})
    _patch_container_lock(metadata_json, updates, item_type == "CONTAINER")
    if item_type == "READABLE":
        _patch_text_log(metadata_json, updates)
    ent.metadata_json = metadata_json
    flag_modified(ent, "metadata_json")


def _patch_description(ent: WorldEntity, value: Any) -> None:
    text = str(value).strip()
    is_readable = ent.entity_type == "OBJECT" and str(ent.item_type or "").upper() == "READABLE"
    if is_readable and len(text) > 200:
        raise HTTPException(status_code=400, detail="READABLE descriptions must be <= 200 chars")
    ent.description = text


async def _patch_entity(
    db: AsyncSession,
    template_id: str,
    target_type: str,
    raw_target_id: str,
    updates: dict[str, Any],
) -> str:
    ent = await _resolve_entity_target(
        db=db, template_id=template_id, entity_type=target_type, raw_target_id=raw_target_id
    )
    if ent is None:
        raise _unresolved(target_type, raw_target_id)
    if "name" in updates:
        ent.name = str(updates["name"]).strip()[:120]
    if "description" in updates:
        _patch_description(ent, updates["description"])
    if "is_portable" in updates and ent.entity_type == "OBJECT":
        ent.is_portable = bool(updates["is_portable"])
    if "current_scene_id" in updates:
        new_scene = str(updates["current_scene_id"] or "").strip().upper()
        if not new_scene:
            raise HTTPException(status_code=400, detail="current_scene_id cannot be empty")
        await _ensure_template_scene_exists(db, template_id, new_scene)
        ent.current_scene_id = new_scene

    if ent.entity_type == "NPC":
        _patch_npc_fields(ent, updates)
    elif ent.entity_type == "OBJECT":
        _patch_object_fields(ent, updates)
    return f"{target_type}:{ent.id}"


_TargetPatcher = Callable[[AsyncSession, str, str, dict[str, Any]], Awaitable[str]]
_TARGETED_PATCHERS: dict[str, _TargetPatcher] = {
    "scene": _patch_scene,
    "exit": _patch_exit,
    "npc": lambda db, tid, raw, upd: _patch_entity(db, tid, "npc", raw, upd),
    "object": lambda db, tid, raw, upd: _patch_entity(db, tid, "object", raw, upd),
}


async def _apply_proposal_patch(
    *,
    db: AsyncSession,
    template_id: str,
    adv: AdventureTemplate,
    patch: FixProposalEntityPatch,
) -> Optional[str]:
    """Apply a single FixProposalEntityPatch. Returns a 'type:id' tag on success."""
    if not _allowed_fields_for(patch.target_type):
        raise HTTPException(
            status_code=400, detail=f"Unsupported target_type '{patch.target_type}'"
        )
    updates = _clean_updates(patch.target_type, patch.field_updates)
    if not updates:
        return None

    target_tag = f"{patch.target_type}:{patch.target_id or ''}"
    if patch.target_type == "adventure":
        await _patch_adventure(adv, updates)
        return target_tag
    if patch.target_type == "protagonist":
        await _patch_protagonist(db, template_id, adv, updates)
        return target_tag

    raw_target_id = str(patch.target_id or "").strip()
    if not raw_target_id:
        raise HTTPException(
            status_code=400,
            detail=f"{patch.target_type} patch is missing target_id",
        )
    patcher = _TARGETED_PATCHERS.get(patch.target_type)
    if patcher is None:
        raise HTTPException(
            status_code=400, detail=f"Unsupported target_type '{patch.target_type}'"
        )
    return await patcher(db, template_id, raw_target_id, updates)
