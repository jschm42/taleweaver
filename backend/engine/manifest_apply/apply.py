"""Entry point: apply a validated world manifest to the database."""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.llm_logger import log_structured_event
from backend.core.style_catalog import resolve_style_instruction
from backend.engine.manifest_apply.adventure_meta import (
    apply_adventure_meta,
    apply_final_adventure_fields,
)
from backend.engine.manifest_apply.avatar import StartingItems, persist_avatar
from backend.engine.manifest_apply.context import ApplyContext, StatusCallback, generator_module
from backend.engine.manifest_apply.npcs import persist_npcs
from backend.engine.manifest_apply.objects import ObjectPlacement, persist_objects
from backend.engine.manifest_apply.scenes import persist_exits, persist_scenes
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene

logger = logging.getLogger(__name__)


async def _collect_existing_images(db: AsyncSession, template_id: str) -> dict[str, str]:
    images: dict[str, str] = {}
    for model in (WorldEntity, WorldScene):
        res = await db.execute(select(model).where(model.template_id == template_id))
        images.update({row.id: row.image_url for row in res.scalars().all() if row.image_url})
    return images


async def _clear_world(db: AsyncSession, template_id: str) -> None:
    """Applying a manifest is idempotent: previous world rows are replaced."""
    for model in (WorldScene, WorldExit, WorldEntity):
        await db.execute(delete(model).where(model.template_id == template_id))


def _manifest_counts(manifest: dict[str, Any]) -> dict[str, int]:
    return {
        f"{key[:-1]}_count": len(manifest.get(key, []))
        for key in ("scenes", "exits", "npcs", "objects")
    }


def _objects_with_protagonist_items(
    manifest: dict[str, Any], prot: dict[str, Any]
) -> list[dict[str, Any]]:
    """Adds inline item definitions from the protagonist's inventory/equipment."""
    objects = list(manifest.get("objects", []))
    seen = {o.get("id") for o in objects if isinstance(o, dict) and "id" in o}
    inline = [
        *(prot.get("starting_inventory") or []),
        *(prot.get("starting_equipment") or {}).values(),
    ]
    for item in inline:
        if isinstance(item, dict) and "id" in item and item["id"] not in seen:
            objects.append(item)
            seen.add(item["id"])
    return objects


async def _assign_npc_inventories(
    ctx: ApplyContext, npc_inventories: dict[str, list[str]], resolved: dict[str, dict[str, Any]]
) -> None:
    res = await ctx.db.execute(
        select(WorldEntity).where(
            WorldEntity.template_id == ctx.template_id, WorldEntity.entity_type == "NPC"
        )
    )
    npcs = {npc.id: npc for npc in res.scalars().all()}
    for npc_id, item_ids in npc_inventories.items():
        if item_ids and npc_id in npcs:
            npcs[npc_id].inventory = [resolved[i] for i in item_ids if i in resolved]


async def _report_image_warnings(ctx: ApplyContext) -> None:
    counters = ctx.image_counters
    warnings: list[str] = []
    if counters["moderation"] > 0:
        warnings.append(
            f"Notice: {counters['moderation']} images were blocked by safety filters and replaced with placeholders. "
            "You can regenerate them in the editor with adjusted descriptions."
        )
    requested = bool(ctx.user and ctx.any_image_generation)
    if (
        requested
        and counters["attempts"] > 0
        and counters["successes"] == 0
        and counters["moderation"] == 0
    ):
        warnings.append(
            "Notice: Image generation did not return usable images, so placeholders were used. "
            "You can regenerate visuals later in the editor."
        )
    if warnings and ctx.adventure:
        ctx.adventure.creation_error = " ".join(warnings)  # type: ignore[assignment]
        await ctx.db.commit()


async def _prepare_context(
    db: AsyncSession,
    template_id: str,
    manifest_dict: dict[str, Any],
    user: Optional[User],
    options: dict[str, Any],
) -> ApplyContext:
    wg = generator_module()
    wg.preprocess_manifest_object_ids(manifest_dict)
    adventure = await db.get(AdventureTemplate, template_id)
    styles = options.pop("selected_image_styles")
    if styles is None and adventure:
        styles = adventure.selected_image_styles
    ctx = ApplyContext(
        db=db,
        template_id=template_id,
        manifest=manifest_dict,
        user=user,
        adventure=adventure,
        **options,
    )
    ctx.style_instruction = resolve_style_instruction(
        styles, user.image_styles_catalog if user else None
    )
    logger.info("Applying manifest with style instruction: '%s'", ctx.style_instruction)
    wg._validate_t2i_prerequisites(
        user,
        need_scene_images=ctx.gen_scenes,
        need_npc_images=ctx.gen_npc,
        need_item_images=ctx.gen_items,
        need_protagonist_image=ctx.gen_protagonist_image,
    )
    return ctx


async def _persist_world(ctx: ApplyContext) -> None:
    prot = ctx.manifest.get("protagonist", {})
    placement = ObjectPlacement(starting=StartingItems())
    if prot and ctx.adventure:
        placement.avatar, placement.starting = await persist_avatar(ctx, prot)
        await ctx.commit_and_refresh(refresh_user=False)

    scenes = ctx.manifest.get("scenes", [])
    await persist_scenes(ctx, scenes)
    persist_exits(ctx.db, ctx.template_id, ctx.manifest.get("exits", []))
    await ctx.commit_and_refresh(refresh_user=False)

    default_scene_id = scenes[0]["id"] if scenes else "START"
    npc_inventories = await persist_npcs(ctx, ctx.manifest.get("npcs", []), default_scene_id)
    await ctx.commit_and_refresh(refresh_user=False)
    apply_final_adventure_fields(ctx)

    placement.npc_item_ids = {item_id for ids in npc_inventories.values() for item_id in ids}
    objects = _objects_with_protagonist_items(ctx.manifest, prot)
    resolved = await persist_objects(ctx, objects, default_scene_id, placement)
    await _assign_npc_inventories(ctx, npc_inventories, resolved)
    await ctx.db.commit()


async def apply_manifest(
    db: AsyncSession,
    template_id: str,
    manifest_dict: dict,
    user: Optional[User] = None,
    gen_npc: bool = False,
    gen_items: bool = False,
    gen_scenes: bool = False,
    gen_protagonist_image: bool = False,
    existing_images: Optional[dict] = None,
    source_assets: Optional[dict[str, Any]] = None,
    selected_image_styles: Optional[list[str]] = None,
    status_callback: Optional[StatusCallback] = None,
) -> None:
    """Populate (or re-populate) the world entities based on a manifest dictionary.

    If user is provided, attempts to generate entity images based on flags.
    If existing_images is provided, uses them to restore entity visual states.
    """
    options = {
        "gen_npc": gen_npc,
        "gen_items": gen_items,
        "gen_scenes": gen_scenes,
        "gen_protagonist_image": gen_protagonist_image,
        "source_assets": source_assets,
        "status_callback": status_callback,
        "selected_image_styles": selected_image_styles,
    }
    ctx = await _prepare_context(db, template_id, manifest_dict, user, options)
    counts = _manifest_counts(manifest_dict)
    log_structured_event(
        "adventure.generation.apply_manifest.start", template_id=template_id, **counts
    )

    ctx.existing_images = (
        existing_images
        if existing_images is not None
        else await _collect_existing_images(db, template_id)
    )
    await _clear_world(db, template_id)
    await apply_adventure_meta(ctx)
    await _persist_world(ctx)

    log_structured_event(
        "adventure.generation.apply_manifest.complete",
        template_id=template_id,
        **counts,
        image_attempts=ctx.image_counters["attempts"],
        image_successes=ctx.image_counters["successes"],
    )
    await _report_image_warnings(ctx)
