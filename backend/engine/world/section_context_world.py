"""Scene, character and item blocks of the region prompt (docs/specs/region_builder.md, 5.3).

``compact``: ids, names and where they are, plus what an item unlocks. ``full``: plus
descriptions, character relations and quest-item flags.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from backend.engine.world.section_context import ContextSource, clip, render
from backend.models.world_entity import WorldEntity, WorldScene

_NO_REGION = "(no region)"


def _region_of(src: ContextSource) -> dict[str, str]:
    return {s.id: s.section_id or _NO_REGION for s in src.rows.scenes}


def _scene_full(scene: WorldScene) -> str:
    region = scene.section_id or _NO_REGION
    return f"- {scene.id} ({scene.label}) [{region}]: {clip(scene.description, 400)}"


def scenes_block(src: ContextSource, detail: str) -> tuple[str, int]:
    scenes = sorted(src.rows.scenes, key=lambda s: ((s.section_id or ""), s.id))
    heading = "EXISTING SCENES (ids are taken):"
    if detail == "full":
        return render(heading, [_scene_full(s) for s in scenes]), len(scenes)
    grouped: dict[str, list[str]] = defaultdict(list)
    for scene in scenes:
        grouped[scene.section_id or _NO_REGION].append(f"{scene.id} ({scene.label})")
    entries = [f"- {region}: {', '.join(names)}" for region, names in sorted(grouped.items())]
    return render(heading, entries), len(scenes)


def _relations(entity: WorldEntity) -> str:
    relations = (entity.metadata_json or {}).get("relations") or []
    parts = [
        f"{r.get('npc_id')} ({r.get('kind')})"
        for r in relations
        if isinstance(r, dict) and r.get("npc_id")
    ]
    return f" Relations: {', '.join(parts)}." if parts else ""


def _npc_line(npc: WorldEntity, regions: dict[str, str], detail: str) -> str:
    where = f"at {npc.current_scene_id}, {regions.get(npc.current_scene_id, _NO_REGION)}"
    line = f"- {npc.id} ({npc.name}, {where})"
    if detail != "full":
        return line
    return f"{line}: {clip(npc.description, 300)}{_relations(npc)}"


def npcs_block(src: ContextSource, detail: str) -> tuple[str, int]:
    regions = _region_of(src)
    npcs = sorted((e for e in src.rows.entities if e.entity_type == "NPC"), key=lambda e: e.id)
    entries = [_npc_line(n, regions, detail) for n in npcs]
    return render("EXISTING CHARACTERS (ids are taken):", entries), len(entries)


def _unlocks(src: ContextSource) -> dict[str, list[str]]:
    """Item id -> what it opens (exits and containers)."""
    opens: dict[str, list[str]] = defaultdict(list)
    for ex in src.rows.exits:
        if ex.item_to_unlock:
            opens[ex.item_to_unlock].append(f"exit {ex.from_scene_id} -> {ex.to_scene_id}")
    for ent in src.rows.entities:
        key = (ent.metadata_json or {}).get("item_to_unlock")
        if key:
            opens[str(key)].append(f"container {ent.id}")
    return opens


def _item_line(item: WorldEntity, opens: list[str], detail: str) -> str:
    kind = item.item_type or "ITEM"
    line = f"- {item.id} ({item.name}, {kind}, in {item.current_scene_id})"
    if opens:
        line += f" opens {', '.join(opens)}"
    if detail != "full":
        return line
    quest = " Quest item." if (item.metadata_json or {}).get("quest_item") else ""
    return f"{line}: {clip(item.description, 200)}{quest}"


def items_block(src: ContextSource, detail: str) -> tuple[str, int]:
    opens = _unlocks(src)
    items = sorted((e for e in src.rows.entities if e.entity_type == "OBJECT"), key=lambda e: e.id)
    entries = [_item_line(i, opens.get(i.id, []), detail) for i in items]
    return render(
        "EXISTING ITEMS (ids are taken; reuse them only as keys or references):", entries
    ), len(entries)


def scene_line(scene: Any, limit: int = 240) -> str:
    """One gateway scene: id, label and the start of its description."""
    return f"- {scene.id} ({scene.label}): {clip(scene.description, limit)}"
