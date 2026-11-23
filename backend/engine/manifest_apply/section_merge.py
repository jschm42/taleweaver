"""Merges a generated region (``SectionManifest``) into an existing adventure template.

Unlike ``apply_manifest`` nothing is cleared: the region's scenes, exits, characters and items
go through the same ``persist_*`` steps as a full world (stats, scripts, inventories, voices),
and its quests, awards, chapters and scripts are appended to the adventure. The section
becomes ``built`` with its summary. The region was validated before (``engine/world/section_validation.py``), so its ids are all new.

With the Region Builder's media options the scenes, characters and items get images while
they are persisted (``section_media``). The section keeps a ``generated`` record of every id the
region added, so "Discard region" (``section_discard``) can take it out again.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.engine.manifest_apply.adventure_meta import _clean_sequence
from backend.engine.manifest_apply.apply import _assign_npc_inventories
from backend.engine.manifest_apply.avatar import StartingItems
from backend.engine.manifest_apply.context import ApplyContext, generator_module
from backend.engine.manifest_apply.npcs import persist_npcs
from backend.engine.manifest_apply.objects import ObjectPlacement, persist_objects
from backend.engine.manifest_apply.scenes import persist_exits, persist_scenes
from backend.engine.manifest_apply.section_media import RegionMedia, enable_images, image_notes
from backend.engine.world.sections import normalize_sections
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User

# Manifest lists that mirror the world rows (sessions read scene helpers from the manifest).
_WORLD_LISTS = ("scenes", "exits", "npcs", "objects")


def _append(current: Any, new: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [*(current if isinstance(current, list) else []), *deepcopy(new)]


def _append_story(adventure: AdventureTemplate, region: dict[str, Any]) -> None:
    """Quests, awards, chapters and scripts of the region join the adventure's lists."""
    quests = [{**q, "status": q.get("status") or "open"} for q in region.get("quests") or []]
    awards = [{**a, "is_earned": False} for a in region.get("awards") or []]
    sequences = [_clean_sequence(s) for s in region.get("sequences") or []]
    adventure.quests = _append(adventure.quests, quests)  # type: ignore[assignment]
    adventure.awards = _append(adventure.awards, awards)  # type: ignore[assignment]
    adventure.sequences = _append(adventure.sequences, sequences)  # type: ignore[assignment]
    manifest = (
        deepcopy(adventure.original_manifest)
        if isinstance(adventure.original_manifest, dict)
        else {}
    )
    for key in _WORLD_LISTS:
        manifest[key] = _append(manifest.get(key), region.get(key) or [])
    manifest["quests"] = deepcopy(adventure.quests)
    manifest["awards"] = deepcopy(adventure.awards)
    manifest["sequences"] = deepcopy(adventure.sequences)
    manifest["scripts"] = _append(manifest.get("scripts"), region.get("scripts") or [])
    adventure.original_manifest = manifest  # type: ignore[assignment]
    for column in ("quests", "awards", "sequences", "original_manifest"):
        flag_modified(adventure, column)


def _ids(entries: Any, key: str = "id") -> list[str]:
    return [str(e.get(key)) for e in entries or [] if isinstance(e, dict) and e.get(key)]


def generated_record(region: dict[str, Any], planned_links: list[dict[str, Any]]) -> dict[str, Any]:
    """What the region added, for "Discard region"; ``planned_links`` are restored then."""
    return {
        "scene_ids": _ids(region.get("scenes")),
        "entity_ids": [*_ids(region.get("npcs")), *_ids(region.get("objects"))],
        "quest_ids": _ids(region.get("quests")),
        "award_keys": _ids(region.get("awards"), "key"),
        "sequence_ids": _ids(region.get("sequences")),
        "script_ids": _ids(region.get("scripts")),
        "planned_links": deepcopy(planned_links),
    }


def _mark_built(adventure: AdventureTemplate, section_id: str, region: dict[str, Any]) -> None:
    sections = normalize_sections(adventure.world_sections)
    for section in sections:
        if section["id"] == section_id:
            section.update(status="built", summary=str(region.get("summary") or "")[:4000])
            section["generated"] = generated_record(region, section["planned_links"])
            section["planned_links"] = []
            section.pop("generation_error", None)
    adventure.world_sections = sections  # type: ignore[assignment]
    manifest = (
        deepcopy(adventure.original_manifest)
        if isinstance(adventure.original_manifest, dict)
        else {}
    )
    manifest["sections"] = deepcopy(sections)
    adventure.original_manifest = manifest  # type: ignore[assignment]
    for column in ("world_sections", "original_manifest"):
        flag_modified(adventure, column)


async def _persist_world(ctx: ApplyContext, region: dict[str, Any]) -> None:
    scenes = region.get("scenes") or []
    await persist_scenes(ctx, scenes)
    persist_exits(ctx.db, ctx.template_id, region.get("exits") or [])
    await ctx.commit_and_refresh(refresh_user=False)
    default_scene_id = scenes[0]["id"]
    npc_inventories = await persist_npcs(ctx, region.get("npcs") or [], default_scene_id)
    placement = ObjectPlacement(starting=StartingItems())
    placement.npc_item_ids = {item for ids in npc_inventories.values() for item in ids}
    resolved = await persist_objects(ctx, region.get("objects") or [], default_scene_id, placement)
    await _assign_npc_inventories(ctx, npc_inventories, resolved)
    await ctx.db.flush()


async def merge_section(
    db: AsyncSession,
    template_id: str,
    section_id: str,
    region: dict[str, Any],
    user: Optional[User],
    media: Optional[RegionMedia] = None,
) -> list[str]:
    """Writes the validated region into the template and marks the section built (commits).
    Returns notes about images that were skipped, blocked or failed."""
    adventure = await db.get(AdventureTemplate, template_id)
    if adventure is None:
        raise ValueError(f"Adventure '{template_id}' not found.")
    generator_module().preprocess_manifest_object_ids(region)
    ctx = ApplyContext(
        db=db, template_id=template_id, manifest=region, user=user, adventure=adventure
    )
    notes = enable_images(ctx, media or RegionMedia())
    await _persist_world(ctx, region)
    adventure = await db.get(AdventureTemplate, template_id)
    _append_story(adventure, region)
    _mark_built(adventure, section_id, region)
    await db.commit()
    return [*notes, *image_notes(ctx)]
