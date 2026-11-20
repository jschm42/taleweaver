"""Hidden NPC checks: hidden NPCs appear only through scripts or their reveal guard.

The Game Master never discovers hidden NPCs (``backend.engine.rules.reveal_policy``), so a
natural-language ``reveal_rule`` on an NPC has no effect any more.
"""

from __future__ import annotations

from backend.core.world_validation.context import (
    ValidationContext,
    entity_field,
    entity_id,
    finding,
)
from backend.engine.rules.reveal_policy import is_script_only_reveal
from backend.schemas.validation import ValidationFinding


def _legacy_rule(npc: dict) -> str:
    rule = str(npc.get("reveal_rule") or "").strip()
    return "" if is_script_only_reveal(rule) else rule


def check_hidden_npc_reveal(ctx: ValidationContext) -> list[ValidationFinding]:
    """Warns about NPC reveal rules the engine ignores (kept only for lossless round trips)."""
    findings: list[ValidationFinding] = []
    for npc in ctx.entities_of("NPC"):
        legacy = _legacy_rule(npc)
        if not legacy or not entity_field(npc, "is_hidden"):
            continue
        npc_id = entity_id(npc) or "?"
        findings.append(
            finding(
                "warn",
                "npc_reveal_rule_ignored",
                f"{npc_id} has the reveal rule '{legacy}', but hidden characters are no longer "
                "discovered by the Game Master. Replace it with a reveal guard (Python condition) "
                "or reveal the character from a script.",
                entity_id=npc_id,
            )
        )
    return findings
