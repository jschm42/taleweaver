"""Companion (sidekick) checks (see backend/engine/party)."""

from __future__ import annotations

from backend.core.world_validation.context import (
    ValidationContext,
    entity_field,
    entity_id,
    finding,
)
from backend.engine.party.companion_config import COMPANION_KEY, normalize_companion
from backend.schemas.validation import ValidationFinding


def check_starting_companions(ctx: ValidationContext) -> list[ValidationFinding]:
    """Only one companion can be active, and a starting companion must be visible."""
    starters = [
        npc
        for npc in ctx.entities_of("NPC")
        if (normalize_companion(entity_field(npc, COMPANION_KEY)) or {}).get("starts_in_party")
    ]
    findings: list[ValidationFinding] = []
    if len(starters) > 1:
        ids = [entity_id(npc) or "?" for npc in starters]
        findings.append(
            finding(
                "warn",
                "companion_multiple_starters",
                f"{len(ids)} NPCs start in the party ({', '.join(ids)}), but only one companion "
                f"can be active. {ids[0]} travels with the protagonist; the others wait in their scenes.",
                npc_ids=ids,
            )
        )
    findings.extend(
        finding(
            "warn",
            "companion_starts_hidden",
            f"{entity_id(npc)} starts in the party but is hidden, so the player cannot see the companion.",
            entity_id=entity_id(npc),
        )
        for npc in starters
        if entity_field(npc, "is_hidden")
    )
    return findings
