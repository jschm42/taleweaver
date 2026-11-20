"""NPC conversations for scripts: ``tw.npcs.converse``, relations and overheard topics.

* ``converse(a, b, topic=..., must_convey=...)`` queues a GM direction: the next narration lets
  the two NPCs talk about the topic (like ``say_directed`` for two characters).
* ``converse(a, b, lines=[(a, "..."), (b, "...")])`` prints fixed dialogue lines instead.
* ``relation`` / ``set_relation`` read and change how one NPC sees another.
* ``topic_heard`` / ``mark_topic_heard`` read and change overheard conversation topics.

Changes are recorded as ``changeset.conversation_ops`` (replayed by every changeset applier with
``conversations.ops.apply_conversation_ops``) and mirrored on the local copy, so a script reads
its own changes back.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

from backend.engine.conversations.ops import apply_conversation_op
from backend.engine.conversations.relations import RELATION_KINDS, relation_between
from backend.engine.conversations.state import CONVERSATIONS_STATE_KEY
from backend.engine.scripting.gm_directions import clean_direction, queue_direction

logger = logging.getLogger(__name__)


def conversation_direction(a: Any, b: Any, topic: Any, must_convey: Any) -> str:
    """GM direction for a short talk between two NPCs; empty without a topic."""
    what = clean_direction(topic)
    if not what:
        return ""
    convey = clean_direction(must_convey)
    convey_part = f" The exchange must make this clear to a listener: {convey}." if convey else ""
    return clean_direction(
        f"{a.name} ({a.id}) and {b.name} ({b.id}) talk with each other about {what}, in two to "
        f'four short dialogue lines, each on its own line as Name: "...".{convey_part} They do '
        "not address the protagonist."
    )


class NPCConversationManagerMixin:
    """Conversation methods of ``tw.npcs``; holds the session's conversation state copy."""

    get: Callable[[str], Any]
    _changeset: Any
    conversation_state: dict[str, Any] | None = None

    def load_conversations(self, store: Any) -> None:
        """Seeds the local copy from ``entity_states["__conversations__"]``."""
        self.conversation_state = dict(store) if isinstance(store, dict) else {}

    def _record_conversation(self, op: dict[str, Any]) -> None:
        self._changeset.conversation_ops.append(op)
        if self.conversation_state is None:
            self.conversation_state = {}
        apply_conversation_op(self.conversation_state, op)

    def converse(
        self,
        npc_a: str,
        npc_b: str,
        topic: str = "",
        must_convey: str = "",
        lines: Any = None,
        after: Any = None,
        after_args: Any = None,
    ) -> None:
        """Lets two NPCs talk: fixed ``lines`` [(npc_id, text), ...] or a directed topic.

        NPCs outside the player's scene stay silent; an ``after`` callback still runs.
        """
        a, b = self.get(npc_a), self.get(npc_b)
        if lines:
            for speaker, text in lines:
                self.get(speaker).say(text)
            return
        present = getattr(a, "is_with_player", True) and getattr(b, "is_with_player", True)
        text = conversation_direction(a, b, topic, must_convey) if present else ""
        if not present:
            logger.info("[Script] converse %s/%s: not both in the player's scene.", a.id, b.id)
        queue_direction(self._changeset, text, after, after_args)

    def _view(self, npc_id: str) -> Any:
        npc = self.get(npc_id)
        data = getattr(npc, "_data", None) or {}
        return SimpleNamespace(id=npc.id, metadata_json=data.get("metadata_json"))

    def relation(self, npc_id: str, other_id: str) -> dict[str, str] | None:
        """How ``npc_id`` sees ``other_id``: ``{"kind", "note"}`` or ``None``."""
        states = {CONVERSATIONS_STATE_KEY: self.conversation_state or {}}
        found = relation_between(self._view(npc_id), other_id, states)
        if not found:
            return None
        return {"kind": found["kind"], "note": found.get("note", "")}

    def set_relation(self, npc_id: str, other_id: str, kind: str, note: str = "") -> None:
        """Sets how ``npc_id`` sees ``other_id`` (kind "" or None removes the relation)."""
        value = str(kind or "").strip().upper()
        if value and value not in RELATION_KINDS:
            raise ValueError(
                f"Unknown relation kind '{kind}'. Use one of {', '.join(RELATION_KINDS)}."
            )
        self._record_conversation(
            {
                "op": "set_relation",
                "npc_id": self.get(npc_id).id,
                "other_id": self.get(other_id).id,
                "kind": value,
                "note": str(note or ""),
            }
        )

    def topic_heard(self, topic_id: str) -> bool:
        """True when the protagonist overheard the conversation topic."""
        heard = (self.conversation_state or {}).get("heard") or []
        return str(topic_id) in {str(t) for t in heard}

    def mark_topic_heard(self, topic_id: str, heard: bool = True) -> None:
        """Marks a topic as overheard (or open again with ``heard=False``)."""
        self._record_conversation(
            {"op": "mark_heard" if heard else "unmark_heard", "topic_id": str(topic_id)}
        )
