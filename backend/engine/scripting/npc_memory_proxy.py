"""NPC memory for scripts: ``npc.remember(key, text)``, ``npc.recall(key)``, ``npc.forget()``.

Scripts read and write the same facts the Game Master keeps (``engine/rules/npc_memory.py``).
Calls record ordered ops in ``changeset.npc_memory_ops`` (replayed by every changeset applier
with ``apply_npc_memory_ops``) and mirror them on the manager's local copy, so a script reads
its own changes back. An NPC without memory slots ignores ``remember`` (debug note), like
the Game Master's reports.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from backend.engine.rules.npc_memory import (
    MAX_MEMORY_SLOTS,
    NPC_MEMORY_STATE_KEY,
    apply_memory_op,
    memory_key,
    memory_slots,
    read_memories,
)


class NPCMemoryMixin:
    """Memory methods of ``NPCProxy``."""

    id: str
    _data: dict[str, Any]
    _changeset: Any
    _entity_mgr: Any

    def _memory_states(self) -> dict[str, Any]:
        return getattr(self._entity_mgr, "memory_states", None) or {}

    def _record_memory(self, op: dict[str, Any]) -> None:
        self._changeset.npc_memory_ops.append(op)
        mgr = self._entity_mgr
        if mgr is not None:
            mgr.memory_states = apply_memory_op(self._memory_states(), op)

    @property
    def memory_slots(self) -> int:
        """How many facts this NPC can keep (0 = no memory)."""
        return memory_slots(self._data.get("metadata_json"))

    @property
    def memories(self) -> list[dict[str, str]]:
        """The NPC's facts about the protagonist, oldest first: ``[{"key", "text"}, ...]``."""
        # Without slots (or entity data, e.g. in guards) every stored fact is returned.
        facts = read_memories(self._memory_states(), self.id, self.memory_slots or None)
        return [{"key": str(f.get("key")), "text": str(f.get("text"))} for f in facts]

    def remember(self, key: str, text: str) -> None:
        """Stores a fact (same key = update, empty text = forget); needs memory slots."""
        slots = self.memory_slots
        if not slots:
            debug = getattr(self._entity_mgr, "debug", None)
            if callable(debug):
                debug(f"remember ignored: {self.id} has no memory slots.")
            return
        self._record_memory(
            {
                "npc_id": self.id,
                "key": memory_key(key, text),
                "text": str(text or ""),
                "slots": slots,
            }
        )

    def recall(self, key: str) -> str:
        """The fact stored under ``key``; "" when the NPC does not remember it."""
        wanted = memory_key(key, "")
        return next((f["text"] for f in self.memories if f["key"] == wanted), "")

    def recalls(self, key: str) -> bool:
        """True when the NPC remembers a fact under ``key``."""
        return bool(self.recall(key))

    def forget(self, key: Any = None) -> None:
        """Forgets one fact, or every fact without a key."""
        if key is None:
            self._record_memory({"npc_id": self.id, "clear": True})
            return
        if self.recalls(key):
            self._record_memory(
                {
                    "npc_id": self.id,
                    "key": memory_key(key, ""),
                    "text": "",
                    "slots": self.memory_slots or MAX_MEMORY_SLOTS,
                }
            )


class NPCMemoryManagerMixin:
    """``tw.npcs.remember(npc_id, key, text)`` and friends; holds the session's memory copy."""

    get: Callable[[str], Any]
    memory_states: dict[str, Any] | None = None
    debug: Callable[[str], None] | None = None

    def load_memories(self, store: Any) -> None:
        """Seeds the local copy from ``entity_states["__npc_memory__"]``."""
        self.memory_states = {NPC_MEMORY_STATE_KEY: dict(store)} if isinstance(store, dict) else {}

    def remember(self, npc_id: str, key: str, text: str) -> None:
        self.get(npc_id).remember(key, text)

    def recall(self, npc_id: str, key: str) -> str:
        return self.get(npc_id).recall(key)

    def recalls(self, npc_id: str, key: str) -> bool:
        return self.get(npc_id).recalls(key)

    def forget(self, npc_id: str, key: Any = None) -> None:
        self.get(npc_id).forget(key)

    def memories(self, npc_id: str) -> list[dict[str, str]]:
        return self.get(npc_id).memories
