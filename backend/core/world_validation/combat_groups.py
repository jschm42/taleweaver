"""NPC combat group checks (see backend/engine/combat/groups.py)."""

from __future__ import annotations

from collections import defaultdict

from backend.core.world_validation.context import (
    ValidationContext,
    entity_field,
    entity_id,
    finding,
)
from backend.engine.combat.groups import normalize_group
from backend.schemas.validation import ValidationFinding


def check_lonely_combat_groups(ctx: ValidationContext) -> list[ValidationFinding]:
    """A combat group with a single NPC never pulls anyone into a fight."""
    members: dict[str, list[str]] = defaultdict(list)
    for npc in ctx.entities_of("NPC"):
        group = normalize_group(entity_field(npc, "combat_group"))
        if group:
            members[group].append(entity_id(npc) or "?")
    return [
        finding(
            "warn",
            "combat_group_single_member",
            f"Combat group '{group}' only contains {ids[0]}, so nobody joins its fights. "
            "Give the allies the same group or remove it.",
            group=group,
            npc_ids=ids,
        )
        for group, ids in sorted(members.items())
        if len(ids) == 1
    ]
