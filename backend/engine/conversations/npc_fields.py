"""The NPC conversation fields in ``metadata_json`` and their stored form.

* ``relations``: list of ``{npc_id, kind, note?}`` (``relations.py``).
* ``chatty``: ``False`` keeps the NPC out of conversations the engine starts; only ``False``
  is stored (the default is to take part).
* ``conversation_topics``: authored topics (``topics.py``).

Every writer (manifest applier, editor, AI fix) goes through ``store_conversation_fields`` or
``normalize_conversation_metadata`` so the stored form stays the same everywhere.
"""

from __future__ import annotations

from typing import Any

from backend.engine.conversations.chatter import CHATTY_KEY
from backend.engine.conversations.relations import RELATIONS_KEY, normalize_relations
from backend.engine.conversations.topics import TOPICS_KEY, normalize_topics

CONVERSATION_FIELDS = (RELATIONS_KEY, CHATTY_KEY, TOPICS_KEY)

__all__ = [
    "CHATTY_KEY",
    "CONVERSATION_FIELDS",
    "RELATIONS_KEY",
    "TOPICS_KEY",
    "conversation_fields",
    "normalize_conversation_metadata",
    "store_conversation_fields",
]


def _store(metadata: dict[str, Any], key: str, raw: Any) -> None:
    if key == CHATTY_KEY:
        value: Any = False if raw is False or str(raw).lower() in ("false", "no", "off") else None
    elif key == RELATIONS_KEY:
        value = normalize_relations(raw) or None
    else:
        value = normalize_topics(raw) or None
    if value is None:
        metadata.pop(key, None)
    else:
        metadata[key] = value


def normalize_conversation_metadata(metadata: dict[str, Any]) -> None:
    """Normalizes the conversation fields of an NPC ``metadata_json`` in place."""
    for key in CONVERSATION_FIELDS:
        _store(metadata, key, metadata.get(key))


def store_conversation_fields(metadata: dict[str, Any], values: dict[str, Any]) -> None:
    """Writes the conversation fields present in ``values`` (``None`` values are skipped)."""
    for key in CONVERSATION_FIELDS:
        if key in values and values[key] is not None:
            _store(metadata, key, values[key])


def conversation_fields(metadata: Any) -> dict[str, Any]:
    """The editor view: relations and topics as lists, chatty as a boolean."""
    data = metadata if isinstance(metadata, dict) else {}
    return {
        RELATIONS_KEY: normalize_relations(data.get(RELATIONS_KEY)),
        CHATTY_KEY: data.get(CHATTY_KEY) is not False,
        TOPICS_KEY: normalize_topics(data.get(TOPICS_KEY)),
    }
