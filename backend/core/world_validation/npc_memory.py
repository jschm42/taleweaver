"""NPC memory checks: memory costs prompt tokens, so it belongs to characters worth talking to.

An NPC that attacks on sight never holds a conversation in which it could learn something
about the protagonist (``backend.engine.rules.npc_memory``).
"""

from __future__ import annotations

from backend.core.world_validation.context import (
    ValidationContext,
    entity_field,
    entity_id,
    finding,
)
from backend.engine.rules.npc_memory import MEMORY_SLOTS_KEY, memory_slots
from backend.schemas.validation import ValidationFinding


def check_hostile_npc_memory(ctx: ValidationContext) -> list[ValidationFinding]:
    """Warns about memory slots on NPCs that attack the protagonist on sight."""
    findings: list[ValidationFinding] = []
    for npc in ctx.entities_of("NPC"):
        slots = memory_slots({MEMORY_SLOTS_KEY: entity_field(npc, MEMORY_SLOTS_KEY)})
        if not slots or entity_field(npc, "attack_mode") != "ATTACK_ON_SIGHT":
            continue
        npc_id = entity_id(npc) or "?"
        findings.append(
            finding(
                "warn",
                "npc_memory_on_hostile",
                f"{npc_id} attacks on sight but has {slots} memory slots. Characters that never "
                "talk to the protagonist need no memory; set memory slots to 0 to save tokens.",
                entity_id=npc_id,
            )
        )
    return findings
