"""Author-placed entities of a dynamic zone: ``[NPC]`` / ``[Item]`` blocks with ``in: ZONE_ID``.

The rooms of a procedural zone (a dynamic exit) do not exist before the player enters them,
so an entity placed there cannot be a world entity of the template. Before generation,
:func:`move_zone_entities` takes those blocks out of the blueprint and stores their source text
in the zone's ``required_entities`` (the ``in:`` line removed). The world-builder LLM only
learns their ids; at runtime ``engine/world/dynamic_required_entities.py`` creates each of them
once per cluster, in the room of its ``depth:`` (default: the first room generated).
"""

from __future__ import annotations

import re

from backend.engine.blueprint.field_specs import KEY_TABLES, normalize_key
from backend.engine.blueprint.models import Blueprint, BlueprintBlock, BlueprintValue

ZONE_ENTITY_KINDS = ("npc", "item")
REQUIRED_FIELD = "dynamic_zone.required_entities"
MAX_REQUIRED_TEXT = 8000
_KEY_LINE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_ \-]*?)\s*:")


def _zone_key(raw: object) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", str(raw or "").strip().upper()).strip("_")


def dynamic_exit_zones(blueprint: Blueprint) -> dict[str, list[BlueprintBlock]]:
    """Zone key -> the dynamic exit blocks of that zone."""
    zones: dict[str, list[BlueprintBlock]] = {}
    for block in blueprint.of_kind("exit"):
        zone_id = block.fields.get("dynamic_zone.zone_id")
        if zone_id is not None and zone_id.value:
            zones.setdefault(_zone_key(zone_id.value), []).append(block)
    return zones


def zone_of(block: BlueprintBlock, zones: dict[str, list[BlueprintBlock]]) -> str | None:
    """The zone key an NPC or item block is placed in, or None."""
    if block.kind not in ZONE_ENTITY_KINDS:
        return None
    location = block.fields.get("start_scene_id")
    key = _zone_key(location.value) if location is not None else ""
    return key if key in zones else None


def _without_location(block: BlueprintBlock) -> str:
    """The block's source without its ``in:`` line (the room is decided at runtime)."""
    table = KEY_TABLES.get(block.kind, {})
    kept = []
    for line in block.source.splitlines():
        match = _KEY_LINE.match(line)
        spec = table.get(normalize_key(match.group(1))) if match else None
        if spec is not None and spec.target == "start_scene_id":
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def _append_required(exit_block: BlueprintBlock, entity: BlueprintBlock, text: str) -> None:
    current = exit_block.fields.get(REQUIRED_FIELD)
    joined = "\n\n".join(part for part in (current.value if current else "", text) if part)
    exit_block.fields[REQUIRED_FIELD] = BlueprintValue(
        joined[:MAX_REQUIRED_TEXT], "fixed", entity.line
    )
    exit_block.zone_entity_ids.append(entity.ref)


def move_zone_entities(blueprint: Blueprint) -> list[str]:
    """Moves the zone-placed NPC/item blocks into their zone exits; returns the moved ids.

    ``depth:`` of an entity outside a zone has no meaning and is dropped."""
    zones = dynamic_exit_zones(blueprint)
    kept: list[BlueprintBlock] = []
    moved: list[str] = []
    for block in blueprint.blocks:
        zone = zone_of(block, zones)
        if zone is None:
            block.fields.pop("dynamic_depth", None)
            kept.append(block)
            continue
        text = _without_location(block)
        for exit_block in zones[zone]:
            _append_required(exit_block, block, text)
        moved.append(block.ref)
    blueprint.blocks = kept
    return moved
