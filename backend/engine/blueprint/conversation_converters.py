"""Blueprint converters for NPC conversations (relations and conversation topics).

``relation: MARA = rival | owes her money``
``topic: the cellar door left open at night | with: GUARD_B | convey: it is unlocked after
midnight | id: cellar_door | guard: tw.flags.get('met_captain') | on_heard: tw.flags.set('k', True)``
"""

from __future__ import annotations

from typing import Any

from backend.engine.blueprint.converters import normalize_id
from backend.engine.conversations.relations import RELATION_KINDS, normalize_relation
from backend.engine.conversations.topics import normalize_topic

_TOPIC_OPTIONS = {
    "with": "with_npc_id",
    "partner": "with_npc_id",
    "convey": "must_convey",
    "must_convey": "must_convey",
    "id": "id",
    "guard": "guard_expression",
    "on_heard": "on_heard_script",
    "on_heard_text": "on_heard_text",
}


def npc_relation(raw: str) -> dict[str, Any]:
    """``MARA = rival | owes her money`` -> ``{"npc_id", "kind", "note"}``."""
    head, _, note = raw.partition("|")
    target, sep, kind = head.partition("=")
    if not sep:
        raise ValueError(f"expected 'NPC_ID = kind', got '{head.strip()}'")
    relation = normalize_relation(
        {"npc_id": normalize_id(target), "kind": kind.strip(), "note": note.strip()}
    )
    if relation is None:
        raise ValueError(
            f"unknown relation '{kind.strip()}'; use one of: "
            + ", ".join(k.lower() for k in RELATION_KINDS)
        )
    return relation


def _topic_option(topic: dict[str, Any], option: str) -> None:
    key, sep, value = option.partition(":")
    field = _TOPIC_OPTIONS.get(key.strip().lower()) if sep else None
    if field is None:
        raise ValueError(f"unknown topic option '{option.strip()}'")
    topic[field] = normalize_id(value) if field == "with_npc_id" else value.strip()


def conversation_topic(raw: str) -> dict[str, Any]:
    """``<topic> | with: NPC | convey: ... | id: ... | guard: ... | on_heard: ...``."""
    head, *options = [part.strip() for part in raw.split("|")]
    topic: dict[str, Any] = {"topic": head}
    for option in options:
        if option.lower() == "repeatable":
            topic["repeatable"] = True
            continue
        _topic_option(topic, option)
    stored = normalize_topic(topic)
    if stored is None:
        raise ValueError("a topic needs a text before the first '|'")
    return stored
