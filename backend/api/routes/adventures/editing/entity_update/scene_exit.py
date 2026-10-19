"""Updates for scenes (incl. ID rename cascade) and exits (incl. lock gates)."""

from copy import deepcopy

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.editing.common import _normalize_lock_fields
from backend.api.routes.adventures.editing.entity_update.fields import (
    copy_scripts,
    given,
    template_row_exists,
    template_rows,
    validated_new_id,
)
from backend.api.routes.adventures.editing.schemas import EntityUpdateRequest
from backend.models.adventure_template import AdventureTemplate
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene

_SCENE_SCRIPT_FIELDS = (
    "on_enter_scene_script",
    "on_enter_scene_text",
    "on_leave_scene_script",
    "on_leave_scene_text",
)
_EXIT_SCRIPT_FIELDS = (
    "unlock_expression",
    "on_open_exit_script",
    "on_open_exit_text",
    "on_exit_used_script",
    "on_exit_used_text",
    "on_unlock_success_script",
    "on_unlock_success_text",
    "on_unlock_failure_script",
    "on_unlock_failure_text",
)
# Exit columns mirrored into the manifest's exit entries.
_EXIT_MANIFEST_FIELDS = (
    "label",
    "exit_type",
    "is_locked",
    "lock_description",
    "code_to_unlock",
    "item_to_unlock",
    "rule_to_unlock",
    *_EXIT_SCRIPT_FIELDS,
)
_LOCK_FIELDS = ("code_to_unlock", "item_to_unlock", "rule_to_unlock")
_MAX_SCENE_ID_LENGTH = 50
_MAX_DECORATIVE_OBJECTS = 7
_MAX_DECORATIVE_OBJECT_LENGTH = 100


async def _rename_scene(
    db: AsyncSession, template_id: str, adv: AdventureTemplate, scene: WorldScene, raw_id: str
) -> None:
    """Change a scene ID and repoint exits, entities, and the manifest start scene."""
    old_id = scene.id
    new_id = validated_new_id(raw_id, "Scene", _MAX_SCENE_ID_LENGTH)
    if new_id == old_id:
        return
    if await template_row_exists(db, WorldScene, template_id, new_id):
        raise HTTPException(status_code=409, detail=f"Scene ID '{new_id}' already exists")
    if await template_row_exists(db, WorldEntity, template_id, new_id):
        raise HTTPException(status_code=409, detail=f"ID '{new_id}' is already taken by an entity")

    scene.id = new_id
    for world_exit in await template_rows(db, WorldExit, template_id):
        if world_exit.from_scene_id == old_id:
            world_exit.from_scene_id = new_id
        if world_exit.to_scene_id == old_id:
            world_exit.to_scene_id = new_id
    for ent in await template_rows(db, WorldEntity, template_id):
        if ent.current_scene_id == old_id:
            ent.current_scene_id = new_id

    manifest = deepcopy(adv.original_manifest or {})
    if manifest.get("start_scene_id") == old_id:
        manifest["start_scene_id"] = new_id
        adv.original_manifest = manifest


def _decorative_objects(values: list[str]) -> list[str] | None:
    decor: list[str] = []
    for value in values:
        stripped = value.strip()
        if len(stripped) > _MAX_DECORATIVE_OBJECT_LENGTH:
            raise HTTPException(
                status_code=400,
                detail="Each decorative object must be at most 100 characters.",
            )
        if stripped:
            decor.append(stripped)
    return decor[:_MAX_DECORATIVE_OBJECTS] or None


def _sync_scene_manifest(adv: AdventureTemplate, scene: WorldScene) -> None:
    manifest = adv.original_manifest
    if not isinstance(manifest, dict) or not isinstance(manifest.get("scenes"), list):
        return
    manifest = deepcopy(manifest)
    for item in manifest["scenes"]:
        if isinstance(item, dict) and item.get("id") == scene.id:
            item.update({f: getattr(scene, f) for f in _SCENE_SCRIPT_FIELDS})
    adv.original_manifest = manifest
    flag_modified(adv, "original_manifest")


async def update_scene(
    db: AsyncSession, template_id: str, adv: AdventureTemplate, payload: EntityUpdateRequest
) -> None:
    rows = await template_rows(db, WorldScene, template_id, WorldScene.id == payload.target_id)
    if not rows:
        return
    scene = rows[0]
    if given(payload, "new_id"):
        await _rename_scene(db, template_id, adv, scene, payload.new_id or "")
    if given(payload, "name"):
        scene.label = payload.name
    if given(payload, "description"):
        scene.description = (payload.description or "").strip()
    if given(payload, "decorative_objects"):
        scene.decorative_objects = _decorative_objects(payload.decorative_objects or [])
        flag_modified(scene, "decorative_objects")
    copy_scripts(scene, payload, _SCENE_SCRIPT_FIELDS)
    _sync_scene_manifest(adv, scene)


def _update_exit_lock(world_exit: WorldExit, payload: EntityUpdateRequest) -> None:
    """Only one of code/item/rule gates an exit (code > item > rule)."""
    current = {f: getattr(world_exit, f) or "" for f in _LOCK_FIELDS}
    sent = {f: str(getattr(payload, f) or "") for f in _LOCK_FIELDS if given(payload, f)}
    code, item, rule = _normalize_lock_fields(**{**current, **sent})
    if (code or item or rule) and not str(world_exit.lock_description or "").strip():
        raise HTTPException(
            status_code=400,
            detail="A lock description is required when a code, item, or rule gate is configured on an exit.",
        )
    world_exit.code_to_unlock = code
    world_exit.item_to_unlock = item
    world_exit.rule_to_unlock = rule


def _sync_exit_manifest(adv: AdventureTemplate, world_exit: WorldExit) -> None:
    manifest = adv.original_manifest
    if not isinstance(manifest, dict) or not isinstance(manifest.get("exits"), list):
        return
    manifest = deepcopy(manifest)
    route = (world_exit.from_scene_id, world_exit.to_scene_id)
    for item in manifest["exits"]:
        if not isinstance(item, dict):
            continue
        if (
            item.get("id") != world_exit.id
            and (
                item.get("from_scene_id"),
                item.get("to_scene_id"),
            )
            != route
        ):
            continue
        item.update({f: getattr(world_exit, f) for f in _EXIT_MANIFEST_FIELDS})
        item["is_bidirectional"] = world_exit.exit_type == "bidirectional"
    adv.original_manifest = manifest
    flag_modified(adv, "original_manifest")


async def update_exit(
    db: AsyncSession, template_id: str, adv: AdventureTemplate, payload: EntityUpdateRequest
) -> None:
    res = await db.execute(
        select(WorldExit).where(
            WorldExit.template_id == template_id, WorldExit.id == payload.target_id
        )
    )
    world_exit = res.scalars().first()
    if not world_exit:
        return
    if given(payload, "name"):
        world_exit.label = payload.name
    if given(payload, "locked"):
        world_exit.is_locked = bool(payload.locked)
    if given(payload, "description"):
        world_exit.lock_description = payload.description
    if given(payload, "exit_type"):
        world_exit.exit_type = payload.exit_type
    copy_scripts(world_exit, payload, _EXIT_SCRIPT_FIELDS)
    if any(given(payload, f) for f in _LOCK_FIELDS):
        _update_exit_lock(world_exit, payload)
    _sync_exit_manifest(adv, world_exit)
