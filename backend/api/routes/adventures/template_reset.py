"""Rebuild a template's world (scenes, NPCs, objects) from its original manifest."""

from typing import Any, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.engine.image_prompt_context import clean_appearance
from backend.engine.manifest_apply.objects import recipe_metadata, recipe_result_ids, starts_hidden
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.world_entity import WorldEntity, WorldScene
from backend.utils.text_utils import slugify


def _empty_lock() -> dict[str, str]:
    return {"code_to_unlock": "", "item_to_unlock": "", "rule_to_unlock": ""}


def _container_unlock(obj_def: dict[str, Any]) -> dict[str, str]:
    """Normalize the unlock requirement; the first of code > item > rule wins."""
    lock = _empty_lock()
    code = str(obj_def.get("code_to_unlock") or "").strip()
    item = str(obj_def.get("item_to_unlock") or "").strip().upper()
    rule = str(obj_def.get("rule_to_unlock") or "").strip()
    if code:
        lock["code_to_unlock"] = code[:32]
    elif item:
        lock["item_to_unlock"] = slugify(item).upper().replace("-", "_")[:64]
    elif rule:
        lock["rule_to_unlock"] = rule[:500]
    return lock


def _object_metadata(obj_def: dict[str, Any], item_type: str) -> dict[str, Any]:
    if item_type == "CONSTRUCTABLE":
        return recipe_metadata(obj_def)
    if item_type != "CONTAINER":
        return {}
    lock = _container_unlock(obj_def)
    return {**lock, "locked": any(lock.values())}


def _scene_from_def(
    scene_def: dict[str, Any], template_id: str, images: dict[str, Optional[str]]
) -> WorldScene:
    scene_id = scene_def["id"]
    return WorldScene(
        id=scene_id,
        template_id=template_id,
        label=scene_def.get("name") or scene_def.get("label") or scene_id,
        description=scene_def.get("description", ""),
        image_url=images.get(scene_id),
    )


def _npc_from_def(
    npc_def: dict[str, Any], template_id: str, images: dict[str, Optional[str]]
) -> WorldEntity:
    return WorldEntity(
        id=npc_def["id"],
        template_id=template_id,
        entity_type="NPC",
        name=npc_def.get("name", ""),
        description=npc_def.get("description", ""),
        appearance=clean_appearance(npc_def.get("appearance")),
        current_scene_id=npc_def.get("start_scene_id"),
        image_url=images.get(npc_def["id"]),
    )


def _object_from_def(
    obj_def: dict[str, Any],
    template_id: str,
    images: dict[str, Optional[str]],
    result_ids: set[str],
) -> WorldEntity:
    item_type = str(obj_def.get("item_type") or "PICKABLE").upper()
    return WorldEntity(
        id=obj_def["id"],
        template_id=template_id,
        entity_type="OBJECT",
        name=obj_def.get("name", ""),
        description=obj_def.get("description", ""),
        appearance=clean_appearance(obj_def.get("appearance")),
        current_scene_id=obj_def.get("start_scene_id"),
        image_url=images.get(obj_def["id"]),
        spatial_position=obj_def.get("spatial_position"),
        item_type=item_type,
        wearable_slots=obj_def.get("wearable_slots") or [],
        is_hidden=starts_hidden(obj_def, result_ids),
        reveal_rule=obj_def.get("reveal_rule") or None,
        unlock_rule=None,
        is_portable=bool(obj_def.get("is_portable", True)),
        combination_ingredients=obj_def.get("combination_ingredients") or [],
        reveals_item_id=obj_def.get("reveals_item_id") or None,
        inventory=obj_def.get("inventory") or [],
        metadata_json=_object_metadata(obj_def, item_type),
    )


async def _image_urls(db: AsyncSession, model: Any, template_id: str) -> dict[str, Optional[str]]:
    rows = await db.execute(select(model).where(model.template_id == template_id))
    return {row.id: row.image_url for row in rows.scalars().all()}


async def _restore_protagonist(
    db: AsyncSession, template_id: str, prot_def: dict[str, Any]
) -> None:
    """Restore static protagonist fields; keep the generated profile image."""
    if not prot_def:
        return
    av_res = await db.execute(
        select(Avatar)
        .where(Avatar.template_id == template_id)
        .order_by(Avatar.created_at.asc(), Avatar.id.asc())
        .limit(1)
    )
    avatar = av_res.scalars().first()
    if not avatar:
        return
    avatar.name = prot_def.get("name") or avatar.name
    avatar.role = prot_def.get("role") or avatar.role
    avatar.description = prot_def.get("description") or avatar.description
    avatar.appearance = clean_appearance(prot_def.get("appearance")) or avatar.appearance


def _with_ids(definitions: list[Any]) -> list[dict[str, Any]]:
    return [d for d in definitions if isinstance(d, dict) and d.get("id")]


async def rebuild_template_world(db: AsyncSession, adv: AdventureTemplate) -> None:
    """Replace template-level scenes/entities with the manifest version, preserving image URLs."""
    template_id = adv.id
    manifest = adv.original_manifest or {}
    scene_images = await _image_urls(db, WorldScene, template_id)
    entity_images = await _image_urls(db, WorldEntity, template_id)

    await db.execute(delete(WorldScene).where(WorldScene.template_id == template_id))
    await db.execute(delete(WorldEntity).where(WorldEntity.template_id == template_id))

    for scene_def in _with_ids(manifest.get("scenes", [])):
        db.add(_scene_from_def(scene_def, template_id, scene_images))
    for npc_def in _with_ids(manifest.get("npcs", [])):
        db.add(_npc_from_def(npc_def, template_id, entity_images))
    objects = _with_ids(manifest.get("objects", []))
    result_ids = recipe_result_ids(objects)
    for obj_def in objects:
        db.add(_object_from_def(obj_def, template_id, entity_images, result_ids))

    await _restore_protagonist(db, template_id, manifest.get("protagonist", {}))
