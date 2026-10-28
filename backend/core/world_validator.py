"""Structural adventure-template validator.

Pure-function linter that walks the editor payload (AdventureTemplateDebugResponse)
and emits ValidationFinding objects. No LLM, no I/O — fully deterministic and fast.

The checks are intentionally conservative: only emit findings the engine can prove
from the data structure. Speculative or narrative judgments belong in the AI pass.
The individual checks live in :mod:`backend.core.world_validation`.
"""

from collections.abc import Callable
from typing import Any

from backend.core.script_validator import check_scripts_and_guards
from backend.core.world_validation import entities, progression, recipes, story, topology
from backend.core.world_validation.context import ValidationContext
from backend.schemas.validation import ValidationFinding

Check = Callable[[ValidationContext], list[ValidationFinding]]

CHECKS: tuple[Check, ...] = (
    story.check_empty_adventure,
    topology.check_unreachable_scenes,
    topology.check_exit_targets_exist,
    topology.check_exit_labels,
    topology.check_exit_locks,
    topology.check_duplicate_ids,
    topology.check_entity_placement,
    topology.check_npc_allowed_scenes,
    progression.check_key_progression,
    entities.check_item_references,
    entities.check_container_inventory,
    recipes.check_constructable_recipes,
    entities.check_switch_state_consistency,
    entities.check_npc_stats,
    entities.check_npc_references,
    entities.check_reveal_targets,
    entities.check_protagonist_items,
    story.check_image_coverage,
    story.check_combat_needs_rpg_mode,
    story.check_story_fields,
    story.check_decorative_objects_overflow,
    story.check_hard_rule_references,
)

_SEVERITY_ORDER = {"error": 0, "warn": 1}


def validate_adventure(payload: Any) -> list[ValidationFinding]:
    """Run the structural validator over a debug payload.

    Accepts either an AdventureTemplateDebugResponse instance or a plain dict
    with the same shape (``adventure``, ``protagonist``, ``scenes``, ``npcs``,
    ``objects``, ``exits``, ``entities_all``).
    """
    ctx = ValidationContext.from_payload(payload)

    findings: list[ValidationFinding] = []
    for check in CHECKS:
        findings.extend(check(ctx))
    findings.extend(
        check_scripts_and_guards(ctx.raw, ctx.adventure, ctx.scenes, ctx.entities, ctx.exits)
    )

    # Sort: errors first, then by code (stable order for UI).
    findings.sort(key=lambda f: (_SEVERITY_ORDER.get(f.severity, 99), f.code, f.location or ""))
    return findings


__all__ = ["CHECKS", "ValidationFinding", "check_scripts_and_guards", "validate_adventure"]
