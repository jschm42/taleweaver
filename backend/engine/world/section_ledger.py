"""The world ledger: what already exists in an adventure, read from the database.

Built fresh for every region generation, never stored and never written by an LLM. It is the
reference ``section_validation`` checks a generated region against (ids, keys, chapters),
whatever context the author chose to put into the prompt. The prompt text comes from
``section_context`` (spec: docs/specs/region_builder.md, section 5).
Spec: docs/specs/world_sections.md (9.2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.world_entity import WorldEntity, WorldExit, WorldScene


@dataclass
class WorldRows:
    """The template rows of an adventure (no session copies)."""

    scenes: list[WorldScene] = field(default_factory=list)
    exits: list[WorldExit] = field(default_factory=list)
    entities: list[WorldEntity] = field(default_factory=list)


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


async def load_world_rows(db: AsyncSession, template_id: str) -> WorldRows:
    return WorldRows(
        scenes=await _rows(db, WorldScene, template_id),
        exits=await _rows(db, WorldExit, template_id),
        entities=await _rows(db, WorldEntity, template_id),
    )


def _sequence_orders(adventure: Any) -> set[int]:
    orders = set()
    for seq in getattr(adventure, "sequences", None) or []:
        try:
            orders.add(int(seq.get("order")))
        except (TypeError, ValueError):
            continue
    return orders


def _keys(entries: Any, key: str) -> set[str]:
    return {str(e.get(key)) for e in entries or [] if isinstance(e, dict) and e.get(key)}


def ledger_from_rows(adventure: Any, rows: WorldRows) -> Ledger:
    return Ledger(
        scene_ids={s.id for s in rows.scenes},
        entity_ids={e.id for e in rows.entities},
        item_ids={e.id for e in rows.entities if e.entity_type == "OBJECT"},
        quest_ids=_keys(getattr(adventure, "quests", None), "id"),
        award_keys=_keys(getattr(adventure, "awards", None), "key"),
        script_ids=_keys(getattr(adventure, "scripts", None), "id"),
        sequence_orders=_sequence_orders(adventure),
        scene_sections={s.id: s.section_id for s in rows.scenes},
    )


async def build_ledger(db: AsyncSession, adventure: Any) -> Ledger:
    """The ledger of an adventure template's current content."""
    return ledger_from_rows(adventure, await load_world_rows(db, adventure.id))
