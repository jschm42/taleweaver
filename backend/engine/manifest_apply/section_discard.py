"""Discard a region the Region Builder built: take out what it added, plan it again.

Uses the section's ``generated`` record (written by ``section_merge``): its scenes, the exits
touching them, its characters and items plus any other entity placed in its scenes, and its
quests, awards, chapters and scripts. The remaining chapters are renumbered 1..n. The section
becomes ``stub`` again with its old planned links, so it can be rebuilt. Only the template
changes: sessions that already took in the region keep their copy. Thread updates of the
campaign outline are not undone. Spec: docs/specs/region_builder.md (phase D).
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy import delete, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.engine.world.sections import normalize_sections
from backend.models.adventure_template import AdventureTemplate
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene


class SectionDiscardError(ValueError):
    """The region cannot be discarded (unknown, not built, or not built by the builder)."""


def _record(adventure: AdventureTemplate, section_id: str) -> dict[str, Any]:
    section = next(
        (s for s in normalize_sections(adventure.world_sections) if s["id"] == section_id), None
    )
    if section is None:
        raise SectionDiscardError(f"Region '{section_id}' not found.")
    if section["status"] != "built" or not section.get("generated"):
        raise SectionDiscardError("Only regions built by the Region Builder can be discarded.")
    return section["generated"]


def _template(model: Any, template_id: str) -> Any:
    return (model.template_id == template_id) & model.session_id.is_(None)


async def _delete_rows(
    db: AsyncSession, template_id: str, record: dict[str, Any]
) -> dict[str, int]:
    scenes = set(record["scene_ids"])
    entities = await db.execute(
        delete(WorldEntity).where(
            _template(WorldEntity, template_id),
            or_(
                WorldEntity.id.in_(record["entity_ids"]),
                WorldEntity.current_scene_id.in_(scenes),
            ),
        )
    )
    exits = await db.execute(
        delete(WorldExit).where(
            _template(WorldExit, template_id),
            or_(WorldExit.from_scene_id.in_(scenes), WorldExit.to_scene_id.in_(scenes)),
        )
    )
    removed_scenes = await db.execute(
        delete(WorldScene).where(_template(WorldScene, template_id), WorldScene.id.in_(scenes))
    )
    return {
        "scenes": removed_scenes.rowcount or 0,
        "exits": exits.rowcount or 0,
        "entities": entities.rowcount or 0,
    }


def _without(entries: Any, key: str, ids: set[str]) -> list[Any]:
    return [e for e in entries or [] if not (isinstance(e, dict) and str(e.get(key)) in ids)]


def _renumbered(sequences: list[Any]) -> list[Any]:
    ordered = sorted(
        (s for s in sequences if isinstance(s, dict)), key=lambda s: int(s.get("order") or 0)
    )
    return [{**s, "order": index} for index, s in enumerate(ordered, start=1)]


def _touches(exit_entry: Any, scenes: set[str]) -> bool:
    if not isinstance(exit_entry, dict):
        return False
    return bool({exit_entry.get("from_scene_id"), exit_entry.get("to_scene_id")} & scenes)


def _clean_story(adventure: AdventureTemplate, record: dict[str, Any]) -> None:
    adventure.quests = _without(adventure.quests, "id", set(record["quest_ids"]))  # type: ignore[assignment]
    adventure.awards = _without(adventure.awards, "key", set(record["award_keys"]))  # type: ignore[assignment]
    sequences = _without(adventure.sequences, "id", set(record["sequence_ids"]))
    adventure.sequences = _renumbered(sequences)  # type: ignore[assignment]
    manifest = (
        deepcopy(adventure.original_manifest)
        if isinstance(adventure.original_manifest, dict)
        else {}
    )
    scenes = set(record["scene_ids"])
    manifest["scenes"] = _without(manifest.get("scenes"), "id", scenes)
    manifest["exits"] = [e for e in manifest.get("exits") or [] if not _touches(e, scenes)]
    for key in ("npcs", "objects"):
        manifest[key] = _without(manifest.get(key), "id", set(record["entity_ids"]))
    manifest["scripts"] = _without(manifest.get("scripts"), "id", set(record["script_ids"]))
    manifest["quests"] = deepcopy(adventure.quests)
    manifest["awards"] = deepcopy(adventure.awards)
    manifest["sequences"] = deepcopy(adventure.sequences)
    adventure.original_manifest = manifest  # type: ignore[assignment]
    for column in ("quests", "awards", "sequences", "original_manifest"):
        flag_modified(adventure, column)


def _replan(adventure: AdventureTemplate, section_id: str, record: dict[str, Any]) -> None:
    sections = normalize_sections(adventure.world_sections)
    for section in sections:
        if section["id"] != section_id:
            continue
        section.update(
            status="stub",
            summary="",
            planned_links=record["planned_links"],
            generated=None,
            generation_notes=[],
            generation_error="",
        )
    sections = normalize_sections(sections)
    adventure.world_sections = sections  # type: ignore[assignment]
    manifest = dict(adventure.original_manifest or {})
    manifest["sections"] = deepcopy(sections)
    adventure.original_manifest = manifest  # type: ignore[assignment]
    flag_modified(adventure, "world_sections")
    flag_modified(adventure, "original_manifest")


async def discard_section(db: AsyncSession, template_id: str, section_id: str) -> dict[str, int]:
    """Removes what the region added and plans it again (commits); returns removed counts."""
    adventure = await db.get(AdventureTemplate, template_id)
    if adventure is None:
        raise SectionDiscardError(f"Adventure '{template_id}' not found.")
    record = _record(adventure, section_id)
    counts = await _delete_rows(db, template_id, record)
    adventure = await db.get(AdventureTemplate, template_id)
    _clean_story(adventure, record)
    _replan(adventure, section_id, record)
    await db.commit()
    counts.update(
        quests=len(record["quest_ids"]),
        awards=len(record["award_keys"]),
        chapters=len(record["sequence_ids"]),
        scripts=len(record["script_ids"]),
    )
    return counts
