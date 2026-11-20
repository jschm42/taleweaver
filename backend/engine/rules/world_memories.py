"""World memories: lasting consequences of the protagonist's actions (``SessionState.world_memories``).

The Game Master records them in ``GameEvent.new_world_memories``, scripts with
``tw.memories.add``. Both go through ``add_world_memory``, which keeps the list bounded:
descriptions are clipped, duplicates skipped, and beyond ``MAX_STORED_MEMORIES`` the oldest
entry is dropped.

``world_memories_prompt_block`` only sends what matters right now, newest first, at most
``MAX_PROMPT_MEMORIES`` lines: global memories, local memories of the current scene, and
memories about a character (``npc_id``) only while that character is in the scene.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any, Optional

MAX_STORED_MEMORIES = 24
MAX_PROMPT_MEMORIES = 8
MEMORY_DESCRIPTION_MAX = 160
SCOPES = ("local", "global")
EMOTIONS = ("positive", "negative", "neutral")


def _clip(text: Any) -> str:
    value = " ".join(str(text or "").split())
    if len(value) <= MEMORY_DESCRIPTION_MAX:
        return value
    return value[: MEMORY_DESCRIPTION_MAX - 1].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"


def _same_place(existing: dict[str, Any], entry: dict[str, Any]) -> bool:
    if existing.get("scope") != entry["scope"]:
        return False
    return entry["scope"] == "global" or (existing.get("scene_id") or "") == (
        entry.get("scene_id") or ""
    )


def is_duplicate(memories: Iterable[dict[str, Any]], entry: dict[str, Any]) -> bool:
    """Same description (case-insensitive) in the same scope (and scene, when local)."""
    wanted = entry["description"].lower()
    return any(
        (m.get("description") or "").strip().lower() == wanted and _same_place(m, entry)
        for m in memories
        if isinstance(m, dict)
    )


def make_world_memory(
    description: Any,
    *,
    scope: Any = "global",
    emotion: Any = "neutral",
    npc_id: Optional[str] = None,
    scene_id: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """A normalized memory entry; ``None`` for an empty description."""
    text = _clip(description)
    if not text:
        return None
    return {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(UTC).isoformat(),
        "description": text,
        "npc_id": str(npc_id).strip().upper() if npc_id else None,
        "emotion": emotion if emotion in EMOTIONS else "neutral",
        "scope": scope if scope in SCOPES else "global",
        "scene_id": scene_id,
    }


def add_world_memory(
    memories: Optional[list[dict[str, Any]]], entry: Optional[dict[str, Any]]
) -> tuple[list[dict[str, Any]], bool]:
    """Appends ``entry`` unless it is empty or a duplicate; keeps the newest entries only."""
    current = [m for m in memories or [] if isinstance(m, dict)]
    if entry is None or is_duplicate(current, entry):
        return current, False
    return [*current, entry][-MAX_STORED_MEMORIES:], True


def _is_relevant(memory: dict[str, Any], scene_id: str, present: set[str]) -> bool:
    npc_id = str(memory.get("npc_id") or "").upper()
    if npc_id and npc_id not in present:
        return False
    if memory.get("scope") == "local":
        return memory.get("scene_id") == scene_id
    return True


def _line(memory: dict[str, Any]) -> str:
    emotion = memory.get("emotion")
    suffix = f" ({emotion})" if emotion in ("positive", "negative") else ""
    return f"- {memory.get('description')}{suffix}"


def world_memories_prompt_block(
    memories: Any, scene_id: Optional[str], present_npc_ids: Iterable[str] = ()
) -> str:
    """The WORLD MEMORIES block: relevant memories only, newest last, at most 8 lines."""
    present = {str(n).upper() for n in present_npc_ids}
    relevant = [
        m
        for m in memories or []
        if isinstance(m, dict) and m.get("description") and _is_relevant(m, scene_id or "", present)
    ][-MAX_PROMPT_MEMORIES:]
    if not relevant:
        return ""
    return "\n\nWORLD MEMORIES (LONG-TERM CONSEQUENCES):\n" + "\n".join(map(_line, relevant))
