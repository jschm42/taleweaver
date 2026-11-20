"""NPC conversation checks: relations and topics must name existing NPCs; topic ids are unique.

Heard topics are stored by id (``engine/conversations/state.py``) and scripts react to them
with ``on_conversation_heard`` (target = topic id), so two topics with the same id would
share one "heard" flag.
"""

from __future__ import annotations

from typing import Any

from backend.core.world_validation.context import (
    ValidationContext,
    entity_field,
    entity_id,
    finding,
)
from backend.engine.conversations.relations import normalize_relations
from backend.engine.conversations.topics import normalize_topics
from backend.schemas.validation import ValidationFinding


def _unknown_ref(npc_id: str, field: str, target: str) -> ValidationFinding:
    return finding(
        "error",
        "conversation_unknown_npc",
        f"{npc_id}: {field} names '{target}', which is no NPC of this adventure.",
        entity_id=npc_id,
    )


def _npc_refs(npc: dict[str, Any], npc_ids: set[str]) -> list[ValidationFinding]:
    npc_id = entity_id(npc) or "?"
    findings = [
        _unknown_ref(npc_id, "a relation", rel["npc_id"])
        for rel in normalize_relations(entity_field(npc, "relations"))
        if rel["npc_id"].upper() not in npc_ids
    ]
    findings.extend(
        _unknown_ref(npc_id, f"topic '{topic['id']}'", topic["with_npc_id"])
        for topic in normalize_topics(entity_field(npc, "conversation_topics"))
        if topic.get("with_npc_id") and str(topic["with_npc_id"]).upper() not in npc_ids
    )
    return findings


def check_conversation_refs(ctx: ValidationContext) -> list[ValidationFinding]:
    """Errors for relations and topic partners that name unknown NPCs."""
    npcs = ctx.entities_of("NPC")
    npc_ids = {str(entity_id(n) or "").upper() for n in npcs}
    return [f for npc in npcs for f in _npc_refs(npc, npc_ids)]


def check_topic_ids(ctx: ValidationContext) -> list[ValidationFinding]:
    """Warns about conversation topic ids used by more than one topic."""
    owners: dict[str, list[str]] = {}
    for npc in ctx.entities_of("NPC"):
        for topic in normalize_topics(entity_field(npc, "conversation_topics")):
            owners.setdefault(topic["id"], []).append(entity_id(npc) or "?")
    return [
        finding(
            "warn",
            "conversation_topic_duplicate_id",
            f"Conversation topic id '{topic_id}' is used {len(ids)} times ({', '.join(ids)}); "
            "give each topic its own id, they share one 'heard' flag otherwise.",
            entity_id=ids[0],
        )
        for topic_id, ids in owners.items()
        if len(ids) > 1
    ]
