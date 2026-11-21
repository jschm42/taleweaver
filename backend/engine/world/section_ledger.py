"""The world ledger: what already exists in an adventure, read from the database.

Built fresh for every region generation, never stored and never written by an LLM. It is the
prompt context that keeps a new region consistent (ids, key items, earlier regions) and the
reference ``section_validation`` checks the generated region against.
Spec: docs/specs/world_sections.md (9.2).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.engine.world.sections import is_stub, normalize_sections
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene

# Prompt budget of the ledger text; long lists are cut with a note.
MAX_LEDGER_CHARS = 14000
_LIST_LIMIT = 80


@dataclass
class Ledger:
    scene_ids: set[str] = field(default_factory=set)
    entity_ids: set[str] = field(default_factory=set)
    item_ids: set[str] = field(default_factory=set)
    quest_ids: set[str] = field(default_factory=set)
    award_keys: set[str] = field(default_factory=set)
    script_ids: set[str] = field(default_factory=set)
    sequence_orders: set[int] = field(default_factory=set)
    scene_sections: dict[str, Optional[str]] = field(default_factory=dict)
    text: str = ""

    @property
    def taken_ids(self) -> set[str]:
        """Every id a new region must not reuse (scenes and entities share one namespace)."""
        return self.scene_ids | self.entity_ids | self.quest_ids | self.script_ids

    def scenes_of(self, section_id: str) -> list[str]:
        return sorted(sid for sid, sec in self.scene_sections.items() if sec == section_id)


async def _rows(db: AsyncSession, model: Any, template_id: str) -> list[Any]:
    res = await db.execute(
        select(model).where(model.template_id == template_id, model.session_id.is_(None))
    )
    return list(res.scalars().all())


def _cut(entries: list[str]) -> list[str]:
    if len(entries) <= _LIST_LIMIT:
        return entries
    return [*entries[:_LIST_LIMIT], f"... and {len(entries) - _LIST_LIMIT} more"]


def _region_lines(adventure: Any) -> list[str]:
    lines = []
    for section in normalize_sections(getattr(adventure, "world_sections", None)):
        state = "planned" if is_stub(section) else "built"
        summary = section["summary"] or section["description"]
        lines.append(f"- {section['id']} {section['label']} [{state}]: {summary[:400]}")
    return lines


def _scene_lines(scenes: list[WorldScene]) -> list[str]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for scene in scenes:
        grouped[scene.section_id or "(no region)"].append(f"{scene.id} ({scene.label})")
    return [f"- {region}: {', '.join(_cut(names))}" for region, names in sorted(grouped.items())]


def _entity_lines(entities: list[WorldEntity]) -> list[str]:
    lines = []
    for ent in entities:
        kind = "NPC" if ent.entity_type == "NPC" else (ent.item_type or "ITEM")
        lines.append(f"{ent.id} ({ent.name}, {kind}, at {ent.current_scene_id})")
    return _cut(lines)


def _lock_lines(exits: list[WorldExit], entities: list[WorldEntity]) -> list[str]:
    """What opens what: key items and codes the new region must not contradict."""
    lines = [
        f"- exit {ex.from_scene_id} -> {ex.to_scene_id} opens with item {ex.item_to_unlock}"
        for ex in exits
        if ex.item_to_unlock
    ]
    for ent in entities:
        key = (ent.metadata_json or {}).get("item_to_unlock") if ent.metadata_json else None
        if key:
            lines.append(f"- container {ent.id} opens with item {key}")
    return _cut(lines)


def _story_lines(adventure: Any) -> list[str]:
    quests = [
        f"{q.get('id')} {q.get('title', '')}" for q in getattr(adventure, "quests", None) or []
    ]
    awards = [
        f"{a.get('key')} {a.get('title', '')}" for a in getattr(adventure, "awards", None) or []
    ]
    chapters = [
        f"{s.get('order')}. {s.get('title', '')}"
        for s in getattr(adventure, "sequences", None) or []
    ]
    scripts = [str(s.get("id")) for s in getattr(adventure, "scripts", None) or [] if s.get("id")]
    return [
        f"Quests: {'; '.join(_cut(quests)) or 'none'}",
        f"Awards: {'; '.join(_cut(awards)) or 'none'}",
        f"Chapters: {'; '.join(chapters) or 'none'}",
        f"Scripts: {', '.join(_cut(scripts)) or 'none'}",
    ]


def _render(adventure: Any, scenes: list, exits: list, entities: list) -> str:
    parts = [
        "WORLD LEDGER (everything that already exists; never reuse these ids):",
        "Regions:",
        *(_region_lines(adventure) or ["- none"]),
        "Scenes by region:",
        *(_scene_lines(scenes) or ["- none"]),
        "Characters and items: " + ("; ".join(_entity_lines(entities)) or "none"),
        "Locks and keys:",
        *(_lock_lines(exits, entities) or ["- none"]),
        *_story_lines(adventure),
    ]
    text = "\n".join(parts)
    return text if len(text) <= MAX_LEDGER_CHARS else text[:MAX_LEDGER_CHARS] + "\n[ledger cut]"


def _sequence_orders(adventure: Any) -> set[int]:
    orders = set()
    for seq in getattr(adventure, "sequences", None) or []:
        try:
            orders.add(int(seq.get("order")))
        except (TypeError, ValueError):
            continue
    return orders


async def build_ledger(db: AsyncSession, adventure: Any) -> Ledger:
    """The ledger of an adventure template's current content."""
    scenes = await _rows(db, WorldScene, adventure.id)
    exits = await _rows(db, WorldExit, adventure.id)
    entities = await _rows(db, WorldEntity, adventure.id)
    return Ledger(
        scene_ids={s.id for s in scenes},
        entity_ids={e.id for e in entities},
        item_ids={e.id for e in entities if e.entity_type == "OBJECT"},
        quest_ids={
            str(q.get("id")) for q in getattr(adventure, "quests", None) or [] if q.get("id")
        },
        award_keys={
            str(a.get("key")) for a in getattr(adventure, "awards", None) or [] if a.get("key")
        },
        script_ids={
            str(s.get("id")) for s in getattr(adventure, "scripts", None) or [] if s.get("id")
        },
        sequence_orders=_sequence_orders(adventure),
        scene_sections={s.id: s.section_id for s in scenes},
        text=_render(adventure, scenes, exits, entities),
    )
