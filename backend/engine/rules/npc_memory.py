"""NPC memory: a few lasting facts a character remembers about the protagonist.

Authors enable it per NPC with ``metadata_json["memory_slots"]`` (0 or missing = off, at most
``MAX_MEMORY_SLOTS``). Enemies and extras simply leave it off.

Pass 1 reports new facts in ``GameEvent.npc_memories`` (``{npc_id, key, text}``);
``api/routes/adventures/npc_memory_flow.py`` validates them and stores them in
``entity_states["__npc_memory__"]`` (``{npc_id: [{"key", "text"}, ...]}``, oldest first), so
they are part of every checkpoint. A known key replaces its fact (the newest fact moves to the
end), an empty text forgets it, and a new key beyond the limit pushes out the oldest fact.

Both passes only see the memories of characters in the current scene
(``npc_memory_prompt_block``): a few short lines per present character, nothing otherwise.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from backend.models.world_entity import WorldEntity

MEMORY_SLOTS_KEY = "memory_slots"
NPC_MEMORY_STATE_KEY = "__npc_memory__"
MAX_MEMORY_SLOTS = 8
DEFAULT_MEMORY_SLOTS = 4
MEMORY_TEXT_MAX = 120
MEMORY_KEY_MAX = 24
MAX_UPDATES_PER_MESSAGE = 3

_KEY_INVALID = re.compile(r"[^a-z0-9]+")

_MECHANICS_HINT = (
    "Report a fact in npc_memories only when the character would still remember it days later: "
    "the protagonist told their name, a promise or deal, an important topic, how the "
    "protagonist treated them. Reuse a key to update a fact, empty text forgets it. English, "
    "one short sentence. Most messages need none."
)


def memory_slots(metadata: Any) -> int:
    """Memory slots an NPC's ``metadata_json`` grants; 0 means the NPC has no memory.

    ``True`` is shorthand for ``DEFAULT_MEMORY_SLOTS``; numbers are clamped to the limit.
    """
    raw = metadata.get(MEMORY_SLOTS_KEY) if isinstance(metadata, dict) else None
    if raw is True:
        return DEFAULT_MEMORY_SLOTS
    if isinstance(raw, bool) or raw is None:
        return 0
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 0
    return max(0, min(MAX_MEMORY_SLOTS, value))


def normalize_memory_slots(raw: Any) -> int | None:
    """Stored form of an authored slot count: ``None`` when off, else 1..MAX_MEMORY_SLOTS."""
    slots = memory_slots({MEMORY_SLOTS_KEY: raw})
    return slots or None


def store_memory_slots(metadata: dict[str, Any], raw: Any) -> None:
    """Writes an authored slot count into an NPC's ``metadata_json`` (removes it when off)."""
    slots = normalize_memory_slots(raw)
    if slots:
        metadata[MEMORY_SLOTS_KEY] = slots
    else:
        metadata.pop(MEMORY_SLOTS_KEY, None)


def _slug(raw: Any) -> str:
    return _KEY_INVALID.sub("_", str(raw or "").lower()).strip("_")[:MEMORY_KEY_MAX].strip("_")


def _clip(raw: Any) -> str:
    text = " ".join(str(raw or "").split())
    if len(text) <= MEMORY_TEXT_MAX:
        return text
    cut = text[: MEMORY_TEXT_MAX - 1].rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:") + "…"


def memory_key(key: Any, text: Any) -> str:
    """Normalized fact key; falls back to the first words of the text."""
    return _slug(key) or _slug(" ".join(str(text or "").split()[:3])) or "fact"


def read_memories(entity_states: Any, npc_id: str, slots: int | None = None) -> list[dict]:
    """The NPC's facts, oldest first; with ``slots`` only the newest ``slots`` facts."""
    store = (entity_states or {}).get(NPC_MEMORY_STATE_KEY)
    entries = store.get(npc_id) if isinstance(store, dict) else None
    facts = [e for e in entries or [] if isinstance(e, dict) and e.get("text")]
    if slots is None:
        return facts
    return facts[-slots:] if slots > 0 else []


def remember(
    entity_states: dict[str, Any], npc_id: str, key: Any, text: Any, slots: int
) -> dict[str, Any]:
    """Stores (or forgets) one fact and returns the new ``entity_states``.

    Returns the given dict unchanged (same object) when nothing changed, so callers can
    tell whether the state needs saving.
    """
    if slots <= 0:
        return entity_states
    fact_key = memory_key(key, text)
    fact_text = _clip(text)
    current = read_memories(entity_states, npc_id, slots)
    kept = [e for e in current if e.get("key") != fact_key]
    if fact_text:
        kept.append({"key": fact_key, "text": fact_text})
    kept = kept[-slots:]
    if kept == current:
        return entity_states
    store = dict((entity_states or {}).get(NPC_MEMORY_STATE_KEY) or {})
    if kept:
        store[npc_id] = kept
    else:
        store.pop(npc_id, None)
    return {**(entity_states or {}), NPC_MEMORY_STATE_KEY: store}


def forget_all(entity_states: dict[str, Any], npc_id: str) -> dict[str, Any]:
    """Drops every fact of the NPC; returns the given dict unchanged when it had none."""
    store = (entity_states or {}).get(NPC_MEMORY_STATE_KEY)
    if not isinstance(store, dict) or npc_id not in store:
        return entity_states
    kept = {k: v for k, v in store.items() if k != npc_id}
    return {**entity_states, NPC_MEMORY_STATE_KEY: kept}


def apply_memory_op(entity_states: dict[str, Any], op: dict[str, Any]) -> dict[str, Any]:
    """One ``tw.npcs`` memory op: ``{npc_id, clear: True}`` or ``{npc_id, key, text, slots}``."""
    npc_id = str(op.get("npc_id") or "")
    if not npc_id:
        return entity_states
    if op.get("clear"):
        return forget_all(entity_states, npc_id)
    return remember(entity_states, npc_id, op.get("key"), op.get("text"), int(op.get("slots") or 0))


def apply_npc_memory_ops(entity_states: dict[str, Any], ops: Any) -> None:
    """Replays the ordered ``ScriptChangeset.npc_memory_ops`` in place (every changeset applier)."""
    updated = entity_states
    for op in ops or []:
        if isinstance(op, dict):
            updated = apply_memory_op(updated, op)
    if updated is not entity_states:
        entity_states[NPC_MEMORY_STATE_KEY] = updated.get(NPC_MEMORY_STATE_KEY) or {}


def _is_out_of_action(entity_states: dict[str, Any], npc: WorldEntity) -> bool:
    own = entity_states.get(str(npc.id)) or {}
    return bool(own.get("is_defeated") or own.get("is_hidden"))


def _memory_npcs(
    entity_states: dict[str, Any], scene_entities: Iterable[WorldEntity]
) -> list[tuple[WorldEntity, int]]:
    rows = []
    for row in scene_entities:
        if str(row.entity_type or "").upper() != "NPC":
            continue
        slots = memory_slots(row.metadata_json)
        if slots and not _is_out_of_action(entity_states, row):
            rows.append((row, slots))
    return rows


def _mechanics_line(entity_states: dict[str, Any], npc: WorldEntity, slots: int) -> str:
    facts = read_memories(entity_states, str(npc.id), slots)
    listed = " | ".join(f"{f['key']}={f['text']}" for f in facts) or "nothing yet"
    return f"- {npc.name} ({npc.id}) [{len(facts)}/{slots}]: {listed}"


def _narration_line(entity_states: dict[str, Any], npc: WorldEntity, slots: int) -> str:
    facts = read_memories(entity_states, str(npc.id), slots)
    if not facts:
        return ""
    return f"- {npc.name}: " + " ".join(f["text"] for f in facts)


def npc_memory_prompt_block(
    entity_states: Any, scene_entities: Iterable[WorldEntity], *, for_mechanics: bool
) -> str:
    """The NPC MEMORY block of the CURRENT STATE; empty without a memory NPC in the scene.

    Pass 1 (``for_mechanics``) sees every present memory NPC with keys and free slots plus the
    rules for ``npc_memories``; Pass 2 only the facts, so it can let them shape the dialogue.
    """
    states = entity_states if isinstance(entity_states, dict) else {}
    npcs = _memory_npcs(states, scene_entities)
    if not npcs:
        return ""
    if for_mechanics:
        lines = [_mechanics_line(states, npc, slots) for npc, slots in npcs]
        head = "\n\nNPC MEMORY (facts these characters keep about the protagonist; used/max):\n"
        return head + "\n".join(lines) + "\n" + _MECHANICS_HINT
    lines = [line for line in (_narration_line(states, n, s) for n, s in npcs) if line]
    if not lines:
        return ""
    head = (
        "\n\nNPC MEMORY (what these characters remember about the protagonist from earlier; "
        "let it shape how they treat and address the protagonist):\n"
    )
    return head + "\n".join(lines)
