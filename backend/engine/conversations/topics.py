"""Authored conversation topics: what two NPCs talk about when the protagonist overhears them.

A topic lives on the NPC who starts it (``metadata_json["conversation_topics"]``)::

    {"id": "cellar_door", "topic": "the cellar door left open at night",
     "with_npc_id": "GUARD_B", "must_convey": "the cellar door is unlocked after midnight",
     "guard_expression": "tw.flags.get('met_captain')", "repeatable": false,
     "on_heard_script": "tw.flags.set('knows_cellar', True)", "on_heard_text": ""}

Only ``topic`` is required. Without ``with_npc_id`` any other present NPC can be the partner.
A topic counts as heard when the engine hands it to the narration (never by parsing the
narration text); then ``on_heard_*`` and the ``on_conversation_heard`` scripts run, and a
non-repeatable topic is never used again.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

TOPICS_KEY = "conversation_topics"
TOPIC_TEXT_MAX = 160
MAX_TOPICS = 12
_ID_INVALID = re.compile(r"[^a-z0-9_]+")


@dataclass(frozen=True)
class ConversationTopic:
    """One normalized topic of ``owner_id``."""

    owner_id: str
    id: str
    topic: str
    with_npc_id: str = ""
    must_convey: str = ""
    guard_expression: str = ""
    repeatable: bool = False
    on_heard_script: str = ""
    on_heard_text: str = ""


def _text(raw: Any, limit: int = TOPIC_TEXT_MAX) -> str:
    return " ".join(str(raw or "").split())[:limit]


def topic_id(raw_id: Any, topic: str) -> str:
    """Normalized topic id; falls back to the first words of the topic."""
    source = str(raw_id or "").strip() or " ".join(topic.split()[:4])
    return _ID_INVALID.sub("_", source.lower()).strip("_")[:40] or "topic"


def normalize_topic(raw: Any) -> dict[str, Any] | None:
    """Stored form of one topic; ``None`` without a topic text."""
    if not isinstance(raw, dict):
        return None
    topic = _text(raw.get("topic"))
    if not topic:
        return None
    stored: dict[str, Any] = {"id": topic_id(raw.get("id"), topic), "topic": topic}
    for key in ("with_npc_id", "guard_expression", "on_heard_script", "on_heard_text"):
        value = str(raw.get(key) or "").strip()
        if value:
            stored[key] = value
    must_convey = _text(raw.get("must_convey"))
    if must_convey:
        stored["must_convey"] = must_convey
    if raw.get("repeatable"):
        stored["repeatable"] = True
    return stored


def normalize_topics(raw: Any) -> list[dict[str, Any]]:
    """Stored topic list (unique ids, at most ``MAX_TOPICS``)."""
    topics: dict[str, dict[str, Any]] = {}
    for entry in raw if isinstance(raw, list) else []:
        topic = normalize_topic(entry)
        if topic and topic["id"] not in topics:
            topics[topic["id"]] = topic
    return list(topics.values())[:MAX_TOPICS]


def topics_of(npc: Any) -> list[ConversationTopic]:
    metadata = getattr(npc, "metadata_json", None)
    raw = metadata.get(TOPICS_KEY) if isinstance(metadata, dict) else None
    owner = str(getattr(npc, "id", "") or "")
    return [
        ConversationTopic(
            owner_id=owner,
            id=t["id"],
            topic=t["topic"],
            with_npc_id=str(t.get("with_npc_id") or ""),
            must_convey=str(t.get("must_convey") or ""),
            guard_expression=str(t.get("guard_expression") or ""),
            repeatable=bool(t.get("repeatable")),
            on_heard_script=str(t.get("on_heard_script") or ""),
            on_heard_text=str(t.get("on_heard_text") or ""),
        )
        for t in normalize_topics(raw)
    ]


def _partner(topic: ConversationTopic, speakers: dict[str, Any]) -> Any:
    if topic.with_npc_id:
        return speakers.get(topic.with_npc_id.upper())
    return next((n for key, n in speakers.items() if key != topic.owner_id.upper()), None)


def pick_topic(
    speakers: Iterable[Any], heard: set[str], guard: Callable[[str], bool]
) -> tuple[ConversationTopic, Any, Any] | None:
    """The first open topic whose owner and partner can talk now: (topic, owner, partner).

    ``guard`` evaluates a ``guard_expression``; it is only called for otherwise usable topics.
    """
    by_id = {str(n.id).upper(): n for n in speakers}
    for owner in by_id.values():
        for topic in topics_of(owner):
            if topic.id in heard and not topic.repeatable:
                continue
            partner = _partner(topic, by_id)
            if partner is None:
                continue
            if topic.guard_expression and not guard(topic.guard_expression):
                continue
            return topic, owner, partner
    return None
