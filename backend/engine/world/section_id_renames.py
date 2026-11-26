"""Renames ids of a generated region that already exist in the adventure.

When the author leaves scenes, characters or items out of the prompt, the LLM cannot see the
taken ids. Instead of rejecting the region, a colliding id becomes ``<ID>_2`` (the next free
number) and every reference inside the region is rewritten: exact string values everywhere,
and whole-word matches inside script code and guard expressions.
Spec: docs/specs/region_builder.md (5.5).
"""

from __future__ import annotations

import re
from typing import Any

from backend.engine.world.section_ledger import Ledger

# (manifest list, id key) of everything that takes an id from the shared namespace.
_COLLECTIONS = (
    ("scenes", "id"),
    ("npcs", "id"),
    ("objects", "id"),
    ("quests", "id"),
    ("scripts", "id"),
    ("awards", "key"),
)
_CODE_KEY = re.compile(r"(_script|_expression|^code)$")
MAX_ID_LENGTH = 50


def _free_id(old: str, taken: set[str]) -> str:
    base = old[: MAX_ID_LENGTH - 4]
    number = 2
    while f"{base}_{number}" in taken:
        number += 1
    return f"{base}_{number}"


def _plan_renames(manifest: dict[str, Any], ledger: Ledger) -> dict[str, str]:
    existing = {i.upper() for i in ledger.taken_ids | ledger.award_keys}
    taken = set(existing)
    renames: dict[str, str] = {}
    for collection, key in _COLLECTIONS:
        for entry in manifest.get(collection) or []:
            old = str(entry.get(key) or "").strip().upper() if isinstance(entry, dict) else ""
            if old in existing and old not in renames:
                renames[old] = _free_id(old, taken)
                taken.add(renames[old])
    return renames


class _Rewriter:
    def __init__(self, renames: dict[str, str]):
        self.renames = renames
        alternatives = "|".join(re.escape(old) for old in sorted(renames, key=len, reverse=True))
        self.pattern = re.compile(rf"\b({alternatives})\b")

    def node(self, node: Any) -> Any:
        if isinstance(node, dict):
            return {key: self.value(key, value) for key, value in node.items()}
        if isinstance(node, list):
            return [self.value("", value) for value in node]
        return node

    def value(self, key: str, value: Any) -> Any:
        if isinstance(value, (dict, list)):
            return self.node(value)
        if not isinstance(value, str):
            return value
        if _CODE_KEY.search(key):
            return self.pattern.sub(lambda m: self.renames[m.group(1)], value)
        return self.renames.get(value.strip().upper(), value)


def rename_collisions(manifest: dict[str, Any], ledger: Ledger) -> list[str]:
    """Renames colliding ids in place; returns one note per rename."""
    renames = _plan_renames(manifest, ledger)
    if not renames:
        return []
    rewritten = _Rewriter(renames).node(manifest)
    manifest.clear()
    manifest.update(rewritten)
    return [
        f"Renamed '{old}' to '{new}': the id already exists in the adventure."
        for old, new in renames.items()
    ]
