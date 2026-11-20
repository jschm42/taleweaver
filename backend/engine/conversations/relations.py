"""How NPCs see each other: ``metadata_json["relations"]``.

An authored relation is ``{"npc_id": "MARA", "kind": "RIVAL", "note": "owes her money"}`` on the
NPC who holds the view. Relations are directed: Bram can call Mara a friend while she sees a
rival. Scripts change them at runtime (``tw.npcs.set_relation``); the overrides live in the
conversation state (``state.py``) and win over the template.

The narration gets an NPC RELATIONS block for NPCs that are present together, so the talk
between them has direction (``relations_prompt_block``).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from backend.engine.conversations.state import read_conversations

RELATIONS_KEY = "relations"
RELATION_KINDS = (
    "FRIEND",
    "FAMILY",
    "PARTNER",
    "ALLY",
    "COLLEAGUE",
    "SUPERIOR",
    "SUBORDINATE",
    "RIVAL",
    "ENEMY",
)
# Relations along which facts about the protagonist travel (gossip).
SHARING_KINDS = frozenset(RELATION_KINDS) - {"RIVAL", "ENEMY"}
RELATION_NOTE_MAX = 80
MAX_RELATIONS = 12


def _kind(raw: Any) -> str:
    value = str(raw or "").strip().upper()
    return value if value in RELATION_KINDS else ""


def _note(raw: Any) -> str:
    return " ".join(str(raw or "").split())[:RELATION_NOTE_MAX]


def normalize_relation(raw: Any) -> dict[str, str] | None:
    """One stored relation, or ``None`` when it names no NPC or no known kind."""
    if not isinstance(raw, dict):
        return None
    npc_id = str(raw.get("npc_id") or "").strip()
    kind = _kind(raw.get("kind"))
    if not npc_id or not kind:
        return None
    relation = {"npc_id": npc_id, "kind": kind}
    note = _note(raw.get("note"))
    if note:
        relation["note"] = note
    return relation


def normalize_relations(raw: Any) -> list[dict[str, str]]:
    """Stored relation list: valid entries, one per target NPC (the last one wins)."""
    by_target: dict[str, dict[str, str]] = {}
    for entry in raw if isinstance(raw, list) else []:
        relation = normalize_relation(entry)
        if relation:
            by_target[relation["npc_id"].upper()] = relation
    return list(by_target.values())[:MAX_RELATIONS]


def _authored(metadata: Any) -> dict[str, dict[str, str]]:
    raw = metadata.get(RELATIONS_KEY) if isinstance(metadata, dict) else None
    return {r["npc_id"].upper(): r for r in normalize_relations(raw)}


def _overrides(entity_states: Any, npc_id: str) -> dict[str, dict[str, str]]:
    store = read_conversations(entity_states).get(RELATIONS_KEY)
    mine = store.get(npc_id.upper()) if isinstance(store, dict) else None
    return {str(k).upper(): v for k, v in mine.items()} if isinstance(mine, dict) else {}


def relations_of(npc: Any, entity_states: Any) -> dict[str, dict[str, str]]:
    """``{other_id_upper: {"npc_id", "kind", "note"?}}`` of ``npc`` (template + script changes)."""
    npc_id = str(getattr(npc, "id", "") or "")
    merged = _authored(getattr(npc, "metadata_json", None))
    for other, override in _overrides(entity_states, npc_id).items():
        relation = normalize_relation({**override, "npc_id": override.get("npc_id") or other})
        if relation:
            merged[other] = relation
        else:
            merged.pop(other, None)
    return merged


def relation_between(npc: Any, other_id: str, entity_states: Any) -> dict[str, str] | None:
    """How ``npc`` sees ``other_id``; ``None`` without a relation."""
    return relations_of(npc, entity_states).get(str(other_id or "").upper())


def related(a: Any, b: Any, entity_states: Any) -> bool:
    """True when either NPC has a relation to the other."""
    return bool(
        relation_between(a, str(b.id), entity_states)
        or relation_between(b, str(a.id), entity_states)
    )


def shares_with(a: Any, b: Any, entity_states: Any) -> bool:
    """True when ``a`` would tell ``b`` what it knows (a relation that is not hostile)."""
    relation = relation_between(a, str(b.id), entity_states)
    return bool(relation and relation["kind"] in SHARING_KINDS)


def _relation_line(npc: Any, relation: dict[str, str], names: dict[str, str]) -> str:
    other = names.get(relation["npc_id"].upper(), relation["npc_id"])
    note = f' ("{relation["note"]}")' if relation.get("note") else ""
    return f"- {npc.name} sees {other} as {relation['kind'].lower()}{note}"


def relations_prompt_block(npcs: Iterable[Any], entity_states: Any) -> str:
    """NPC RELATIONS block for NPCs present together; empty when none of them are related."""
    present = [n for n in npcs if str(getattr(n, "entity_type", "") or "").upper() == "NPC"]
    names = {str(n.id).upper(): str(n.name or n.id) for n in present}
    lines = [
        _relation_line(npc, relation, names)
        for npc in present
        for other, relation in relations_of(npc, entity_states).items()
        if other in names and other != str(npc.id).upper()
    ]
    if not lines:
        return ""
    return (
        "\n\nNPC RELATIONS (how the present characters see each other; let it color how they "
        "talk to and about each other):\n" + "\n".join(lines)
    )
