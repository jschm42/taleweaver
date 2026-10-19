"""Small helpers shared by the entity update handlers."""

import re
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.editing.common import _ensure_template_scene_exists
from backend.api.routes.adventures.editing.schemas import EntityUpdateRequest

_ID_RE = re.compile(r"^[A-Z0-9_]+$")
_MAX_SCENE_REF_LENGTH = 50
_VITALS = (("hp", "max_hp"), ("mana", "max_mana"), ("stamina", "max_stamina"))


def ref_id(item: Any) -> Optional[str]:
    """ID of an inventory/equipment entry (plain ID string or item dict)."""
    if isinstance(item, str):
        return item
    return item.get("id") if isinstance(item, dict) else None


def ref_ids(items: Any) -> set[str]:
    return {rid for rid in (ref_id(i) for i in (items or [])) if rid}


def given(payload: EntityUpdateRequest, field: str) -> bool:
    return getattr(payload, field) is not None


def copy_given(target: Any, payload: EntityUpdateRequest, fields: tuple[str, ...]) -> None:
    """Copy each payload field that was sent onto the same-named attribute."""
    for field in fields:
        if given(payload, field):
            setattr(target, field, getattr(payload, field))


def copy_scripts(target: Any, payload: EntityUpdateRequest, fields: tuple[str, ...]) -> None:
    """Script/text columns: stripped, empty becomes NULL."""
    for field in fields:
        value = getattr(payload, field)
        if value is not None:
            setattr(target, field, value.strip() if value else None)


def put_metadata(
    metadata_json: dict[str, Any],
    payload: EntityUpdateRequest,
    fields: tuple[str, ...],
    *,
    empty_as_none: bool,
) -> None:
    """Store sent script/text fields in ``metadata_json`` (stripped)."""
    for field in fields:
        value = getattr(payload, field)
        if value is None:
            continue
        stripped = value.strip()
        metadata_json[field] = (stripped or None) if empty_as_none else stripped


def apply_vitals(target: Any, payload: EntityUpdateRequest) -> None:
    """hp/mana/stamina also reset their maximum."""
    for field, max_field in _VITALS:
        value = getattr(payload, field)
        if value is not None:
            setattr(target, field, value)
            setattr(target, max_field, value)


def clipped_or_none(value: Optional[str], limit: int) -> Optional[str]:
    normalized = str(value or "").strip()
    return normalized[:limit] if normalized else None


def validated_new_id(raw: str, label: str, max_length: int) -> str:
    new_id = raw.strip().upper()
    if not new_id:
        raise HTTPException(status_code=400, detail=f"{label} ID cannot be empty")
    if not _ID_RE.match(new_id):
        raise HTTPException(
            status_code=400,
            detail=f"{label} ID must contain only uppercase letters, digits, and underscores.",
        )
    if len(new_id) > max_length:
        raise HTTPException(
            status_code=400, detail=f"{label} ID must be at most {max_length} characters."
        )
    return new_id


async def validated_scene_ref(db: AsyncSession, template_id: str, raw: Optional[str]) -> str:
    """Validate a ``current_scene_id`` and make sure the scene exists in the template."""
    scene_id = str(raw or "").strip().upper()
    if not scene_id:
        raise HTTPException(status_code=400, detail="current_scene_id cannot be empty")
    if len(scene_id) > _MAX_SCENE_REF_LENGTH:
        raise HTTPException(
            status_code=400, detail="current_scene_id must be at most 50 characters."
        )
    if not _ID_RE.match(scene_id):
        raise HTTPException(
            status_code=400,
            detail="current_scene_id must contain only uppercase letters, digits, and underscores.",
        )
    await _ensure_template_scene_exists(db, template_id, scene_id)
    return scene_id


async def template_row_exists(db: AsyncSession, model: Any, template_id: str, row_id: str) -> bool:
    res = await db.execute(
        select(model).where(
            model.template_id == template_id,
            model.session_id.is_(None),
            model.id == row_id,
        )
    )
    return res.scalars().first() is not None


async def template_rows(db: AsyncSession, model: Any, template_id: str, *where: Any) -> list[Any]:
    res = await db.execute(
        select(model).where(model.template_id == template_id, model.session_id.is_(None), *where)
    )
    return list(res.scalars().all())
