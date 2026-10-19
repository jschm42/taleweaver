"""Builds and applies ``.twe`` entity bundles for the adventure editor.

Exports a single protagonist, NPC, or item (including its image) and imports such a
bundle into another adventure. NPC/item imports always create a new entity; a
protagonist import replaces the adventure's protagonist profile but keeps its
adventure-specific inventory and equipment.
"""

from __future__ import annotations

import os
import re
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import JSON, Boolean, Column, Integer, String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.assets import _build_uploaded_visual_path
from backend.api.routes.adventures.editor import _get_template_avatar
from backend.api.routes.adventures.logic import AdventureLogic
from backend.core.config import settings
from backend.engine.entity_bundle import (
    IMAGE_EXTENSIONS,
    EntityBundle,
    EntityBundleError,
    pack_entity_bundle,
)
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.world_entity import WorldEntity, WorldScene
from backend.utils.path_security import (
    assert_within_data_dir,
    data_url_to_local_path,
)

KIND_BY_ENTITY_TYPE = {"NPC": "npc", "OBJECT": "item"}
ENTITY_TYPE_BY_KIND = {kind: entity_type for entity_type, kind in KIND_BY_ENTITY_TYPE.items()}
_VISUAL_TARGET_BY_KIND = {"protagonist": "protagonist", "npc": "npc", "item": "object"}

# Columns that belong to the hosting adventure/session and never travel in a bundle.
_ENTITY_EXCLUDED_KEYS = frozenset(
    {"pk", "id", "entity_type", "template_id", "session_id", "created_at", "updated_at"}
)
_ENTITY_IMPORT_COLUMNS = {
    col.name: col for col in WorldEntity.__table__.columns if col.name not in _ENTITY_EXCLUDED_KEYS
}

# Inventory and equipment reference adventure-specific item IDs, so they are not transferred.
_AVATAR_FIELDS = (
    "name",
    "role",
    "description",
    "goal",
    "character",
    "hp",
    "max_hp",
    "stamina",
    "max_stamina",
    "mana",
    "max_mana",
    "exp",
    "strength",
    "dexterity",
    "intelligence",
    "wisdom",
    "charisma",
    "armor_class",
    "stats",
    "status_effects",
)
_AVATAR_IMPORT_COLUMNS = {name: Avatar.__table__.columns[name] for name in _AVATAR_FIELDS}
# Values kept in avatar.stats that the editor mirrors as top-level manifest keys.
_PROTAGONIST_STATS_MANIFEST_KEYS = (
    "on_hp_change_script",
    "on_hp_change_text",
    "on_status_change_script",
    "on_status_change_text",
    "special_actions",
)

_ID_MAX_LENGTH = 30
_ID_INVALID_CHARS = re.compile(r"[^A-Z0-9_]+")


@dataclass
class ImportResult:
    kind: str
    entity_id: str
    name: str
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _TemplateIds:
    scenes: set[str]
    entities: dict[str, str]  # entity id -> entity_type

    @property
    def objects(self) -> set[str]:
        return {eid for eid, etype in self.entities.items() if etype == "OBJECT"}


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def export_entity_bundle(adv: AdventureTemplate, entity: WorldEntity) -> bytes:
    kind = KIND_BY_ENTITY_TYPE.get(str(entity.entity_type or "").upper())
    if not kind:
        raise EntityBundleError("Only NPCs and items can be exported.")
    data = {"id": entity.id}
    for name in _ENTITY_IMPORT_COLUMNS:
        if name != "image_url":
            data[name] = deepcopy(getattr(entity, name))
    image_bytes, image_ext = _read_local_image(entity.image_url)
    return pack_entity_bundle(
        EntityBundle(kind, data, image_bytes, image_ext, source_title=adv.title)
    )


def export_protagonist_bundle(adv: AdventureTemplate, avatar: Avatar) -> bytes:
    data = {name: deepcopy(getattr(avatar, name)) for name in _AVATAR_FIELDS}
    image_bytes, image_ext = _read_local_image(avatar.profile_image)
    return pack_entity_bundle(
        EntityBundle("protagonist", data, image_bytes, image_ext, source_title=adv.title)
    )


def _read_local_image(url: Optional[str]) -> tuple[Optional[bytes], Optional[str]]:
    local_path = data_url_to_local_path(url)
    if not local_path or not os.path.isfile(local_path):
        return None, None
    safe_path = assert_within_data_dir(local_path)
    ext = os.path.splitext(safe_path)[1].lstrip(".").lower()
    if ext not in IMAGE_EXTENSIONS:
        return None, None
    with open(safe_path, "rb") as handle:
        return handle.read(), ext


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


async def import_entity_bundle(
    db: AsyncSession, adv: AdventureTemplate, bundle: EntityBundle
) -> ImportResult:
    """Create a new NPC or item from the bundle inside ``adv``."""
    entity_type = ENTITY_TYPE_BY_KIND.get(bundle.kind)
    if not entity_type:
        raise EntityBundleError(f"Bundle kind '{bundle.kind}' is not an NPC or item.")

    ids = await _load_template_ids(db, adv.id)
    if not ids.scenes:
        raise EntityBundleError("Create at least one scene before importing NPCs or items.")

    values = _coerce_values(bundle.entity, _ENTITY_IMPORT_COLUMNS)
    warnings: list[str] = []
    name = str(values.get("name") or "").strip() or f"Imported {bundle.kind.upper()}"
    new_id = _unique_id(bundle.entity.get("id") or name, set(ids.entities) | ids.scenes)
    if new_id != str(bundle.entity.get("id") or ""):
        warnings.append(f"ID changed to '{new_id}' to avoid a conflict.")

    values.update(
        name=name,
        description=str(values.get("description") or "").strip() or name,
        current_scene_id=await _resolve_scene(db, adv.id, values, ids, warnings),
        is_in_inventory=False,
        image_url=None,
    )
    _drop_missing_references(values, ids, warnings)

    entity = WorldEntity(
        id=new_id, template_id=adv.id, session_id=None, entity_type=entity_type, **values
    )
    entity.image_url = _store_image(adv.id, bundle, new_id)
    db.add(entity)
    await db.commit()
    return ImportResult(bundle.kind, new_id, name, warnings)


async def import_protagonist_bundle(
    db: AsyncSession, adv: AdventureTemplate, bundle: EntityBundle
) -> ImportResult:
    """Replace the adventure protagonist's profile, stats, and portrait with the bundle."""
    if bundle.kind != "protagonist":
        raise EntityBundleError(f"Bundle kind '{bundle.kind}' is not a protagonist.")

    avatar = await _get_template_avatar(db, adv.id)
    if avatar is None:
        avatar = Avatar(user_id=adv.owner_id, template_id=adv.id, name="Hero")
        db.add(avatar)

    for name, value in _coerce_values(bundle.entity, _AVATAR_IMPORT_COLUMNS).items():
        setattr(avatar, name, value)
    avatar.name = str(avatar.name or "").strip() or "Hero"
    flag_modified(avatar, "stats")
    flag_modified(avatar, "status_effects")

    image_url = _store_image(adv.id, bundle, "protagonist")
    if image_url:
        avatar.profile_image = image_url

    _sync_protagonist_manifest(adv, avatar)
    await db.commit()
    return ImportResult("protagonist", str(avatar.id), avatar.name)


def _sync_protagonist_manifest(adv: AdventureTemplate, avatar: Avatar) -> None:
    if not isinstance(adv.original_manifest, dict):
        return
    manifest = deepcopy(adv.original_manifest)
    protagonist = manifest.get("protagonist")
    if not isinstance(protagonist, dict):
        protagonist = {}
    protagonist.update({name: deepcopy(getattr(avatar, name)) for name in _AVATAR_FIELDS})
    protagonist["profile_image"] = avatar.profile_image
    stats = avatar.stats if isinstance(avatar.stats, dict) else {}
    for key in _PROTAGONIST_STATS_MANIFEST_KEYS:
        protagonist[key] = deepcopy(stats.get(key))
    manifest["protagonist"] = protagonist
    adv.original_manifest = manifest
    flag_modified(adv, "original_manifest")


async def _load_template_ids(db: AsyncSession, template_id: str) -> _TemplateIds:
    scene_res = await db.execute(
        select(WorldScene.id).where(
            WorldScene.template_id == template_id, WorldScene.session_id.is_(None)
        )
    )
    entity_res = await db.execute(
        select(WorldEntity.id, WorldEntity.entity_type).where(
            WorldEntity.template_id == template_id, WorldEntity.session_id.is_(None)
        )
    )
    return _TemplateIds(
        scenes=set(scene_res.scalars().all()),
        entities={row.id: str(row.entity_type or "").upper() for row in entity_res.all()},
    )


async def _resolve_scene(
    db: AsyncSession,
    template_id: str,
    values: dict[str, Any],
    ids: _TemplateIds,
    warnings: list[str],
) -> str:
    wanted = str(values.get("current_scene_id") or "")
    if wanted in ids.scenes:
        return wanted
    start_scene = await AdventureLogic.resolve_initial_scene_id(db, template_id)
    target = start_scene if start_scene in ids.scenes else sorted(ids.scenes)[0]
    warnings.append(f"Placed in scene '{target}' (original scene not found).")
    return target


def _drop_missing_references(
    values: dict[str, Any], ids: _TemplateIds, warnings: list[str]
) -> None:
    """Remove links to scenes/items that do not exist in the target adventure."""
    objects = ids.objects

    allowed = [s for s in values.get("allowed_scenes") or [] if s in ids.scenes]
    if len(allowed) != len(values.get("allowed_scenes") or []):
        warnings.append("Removed allowed scenes that do not exist in this adventure.")
    values["allowed_scenes"] = allowed

    inventory = [i for i in values.get("inventory") or [] if _inventory_item_id(i) in objects]
    if len(inventory) != len(values.get("inventory") or []):
        warnings.append("Removed inventory items that do not exist in this adventure.")
    values["inventory"] = inventory

    if values.get("reveals_item_id") and values["reveals_item_id"] not in objects:
        warnings.append(f"Cleared reveal target '{values['reveals_item_id']}' (not found).")
        values["reveals_item_id"] = None

    missing = [i for i in values.get("combination_ingredients") or [] if i not in objects]
    if missing:
        warnings.append(f"Crafting ingredients missing in this adventure: {', '.join(missing)}.")


def _inventory_item_id(item: Any) -> Optional[str]:
    if isinstance(item, dict):
        return item.get("id")
    return item if isinstance(item, str) else None


def _unique_id(raw_id: Any, taken: set[str]) -> str:
    base = _ID_INVALID_CHARS.sub("_", str(raw_id or "").upper()).strip("_")
    base = base[:_ID_MAX_LENGTH] or "IMPORTED"
    candidate = base
    suffix = 1
    while candidate in taken:
        suffix += 1
        tail = f"_{suffix}"
        candidate = f"{base[: _ID_MAX_LENGTH - len(tail)]}{tail}"
    return candidate


def _store_image(template_id: str, bundle: EntityBundle, token: str) -> Optional[str]:
    if not bundle.image_bytes or not bundle.image_ext:
        return None
    full_path = _build_uploaded_visual_path(
        template_id,
        _VISUAL_TARGET_BY_KIND[bundle.kind],
        f"image.{bundle.image_ext}",
        trusted_target_token=token,
    )
    safe_path = assert_within_data_dir(full_path)
    with open(safe_path, "wb") as handle:
        handle.write(bundle.image_bytes)
    rel_path = os.path.relpath(safe_path, settings.DATA_DIR).replace("\\", "/")
    return f"/data/{rel_path}"


# ---------------------------------------------------------------------------
# Value coercion (bundle JSON is untrusted input)
# ---------------------------------------------------------------------------

_MISSING = object()


def _coerce_values(data: dict[str, Any], columns: dict[str, Column]) -> dict[str, Any]:
    coerced: dict[str, Any] = {}
    for name, column in columns.items():
        if name not in data:
            continue
        value = _coerce_column_value(column, data[name])
        if value is not _MISSING:
            coerced[name] = value
    return coerced


def _coerce_column_value(column: Column, value: Any) -> Any:
    if value is None:
        return None if column.nullable else _MISSING
    column_type = column.type
    if isinstance(column_type, Boolean):
        return bool(value)
    if isinstance(column_type, Integer):
        return _coerce_int(value)
    if isinstance(column_type, String):
        return str(value)[: column_type.length] if column_type.length else str(value)
    if isinstance(column_type, JSON):
        return deepcopy(value) if isinstance(value, (dict, list)) else _MISSING
    return _MISSING


def _coerce_int(value: Any) -> Any:
    if isinstance(value, bool):
        return _MISSING
    try:
        return int(value)
    except (TypeError, ValueError):
        return _MISSING
