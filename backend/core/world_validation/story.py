"""Adventure-level, presentation, and hard-rule reference checks."""

from __future__ import annotations

from typing import Any

from backend.core.world_validation.context import (
    ValidationContext,
    entity_id,
    finding,
    metadata,
    scene_id,
)
from backend.schemas.validation import ValidationFinding

DECORATIVE_OBJECTS_CAP = 7
RULES_MIN_LENGTH = 100
WALKTHROUGH_MIN_LENGTH = 50

_STORY_FIELDS = (
    "teaser",
    "rules",
    "plot",
    "intro_text",
    "walkthrough",
    "completed_condition",
    "gameover_condition",
)
# An empty narrative condition is fine when a deterministic guard replaces it.
_GUARD_REPLACES = {
    "completed_condition": "completed_guard_expression",
    "gameover_condition": "gameover_guard_expression",
}
_MIN_LENGTHS = {
    "rules": (RULES_MIN_LENGTH, "rules_too_short", "RPG mode typically needs more guidance"),
    "walkthrough": (
        WALKTHROUGH_MIN_LENGTH,
        "walkthrough_too_short",
        "secret GM notes look thin",
    ),
}
# Hard rule field -> (kind label, attribute of ValidationContext holding valid IDs).
_HARD_RULE_FIELDS = {
    "required_item_id": ("item", "object_ids"),
    "required_scene_id": ("scene", "scene_ids"),
    "required_defeated_npc_id": ("npc", "npc_ids"),
}
_RULE_VERBS = {
    "item": "requires item",
    "scene": "requires entering scene",
    "npc": "requires defeating NPC",
}
_SPECIAL_ACTION_PREFIX = "unlock_"


def check_empty_adventure(ctx: ValidationContext) -> list[ValidationFinding]:
    if (ctx.adventure.get("title") or "").strip():
        return []
    return [finding("error", "empty_adventure", "Adventure has no title.")]


def check_story_fields(ctx: ValidationContext) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for field in _STORY_FIELDS:
        value = (ctx.adventure.get(field) or "").strip()
        guard_field = _GUARD_REPLACES.get(field)
        if not value and guard_field and (ctx.adventure.get(guard_field) or "").strip():
            continue
        if not value:
            findings.append(
                finding(
                    "warn", "empty_story_field", f"Story field '{field}' is empty.", field=field
                )
            )
            continue
        min_length, code, hint = _MIN_LENGTHS.get(field, (0, "", ""))
        if len(value) < min_length:
            findings.append(
                finding(
                    "warn",
                    code,
                    f"Story field '{field}' is only {len(value)} characters — {hint}.",
                    field=field,
                    length=len(value),
                )
            )
    return findings


def _coverage_finding(code: str, label: str, items: list[dict[str, Any]], id_of: Any):
    missing = [i for i in items if not (i.get("image_url") or "").strip()]
    if not missing:
        return None
    return finding(
        "warn",
        code,
        f"{len(missing)} of {len(items)} {label} have no image despite image generation "
        "being enabled.",
        missing_count=len(missing),
        total_count=len(items),
        missing_ids=[id_of(i) for i in missing[:10]],
    )


def check_image_coverage(ctx: ValidationContext) -> list[ValidationFinding]:
    """Warn when image generation is enabled but coverage is < 100%."""
    candidates = (
        ("generate_scene_images", "scene_image_coverage", "scenes", ctx.scenes, scene_id),
        ("generate_npc_images", "npc_image_coverage", "NPCs", ctx.entities_of("NPC"), entity_id),
        (
            "generate_item_images",
            "object_image_coverage",
            "objects",
            ctx.entities_of("OBJECT"),
            entity_id,
        ),
    )
    findings = [
        _coverage_finding(code, label, items, id_of)
        for flag, code, label, items, id_of in candidates
        if ctx.adventure.get(flag)
    ]
    return [f for f in findings if f]


def check_combat_needs_rpg_mode(ctx: ValidationContext) -> list[ValidationFinding]:
    """Explicit combat configuration is dead outside rpg mode (combat/setup.py)."""
    if ctx.is_rpg:
        return []
    aggressive = sorted(
        entity_id(npc) or "?"
        for npc in ctx.entities_of("NPC")
        if metadata(npc).get("attack_mode") == "ATTACK_ON_SIGHT"
        or metadata(npc).get("attack_trigger")
    )
    if not aggressive:
        return []
    return [
        finding(
            "warn",
            "rpg_mode_required_for_combat",
            f"Adventure is in '{ctx.mode}' mode, but NPC(s) {', '.join(aggressive)} are configured "
            "to attack. Combat only runs with rule_enforcement_mode='rpg'.",
            mode=ctx.mode,
            npc_ids=aggressive,
        )
    ]


def check_decorative_objects_overflow(ctx: ValidationContext) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for scene in ctx.scenes:
        decos = scene.get("decorative_objects") or []
        if not isinstance(decos, list) or len(decos) <= DECORATIVE_OBJECTS_CAP:
            continue
        sid = scene_id(scene) or "?"
        findings.append(
            finding(
                "warn",
                "decorative_objects_overflow",
                f"Scene '{sid}' has {len(decos)} decorative objects "
                f"(cap is {DECORATIVE_OBJECTS_CAP}).",
                location=f"scene:{sid}",
                scene_id=sid,
                count=len(decos),
            )
        )
    return findings


def _rule_owners(ctx: ValidationContext) -> list[tuple[str, str, str, dict[str, Any], str]]:
    """(owner kind, owner id, title, rule dict, field prefix) for everything with hard rules."""
    owners: list[tuple[str, str, str, dict[str, Any], str]] = []
    for kind, key, id_field in (
        ("sequence", "sequences", "id"),
        ("quest", "quests", "id"),
        ("award", "awards", "key"),
    ):
        entries = ctx.adventure.get(key)
        for index, entry in enumerate(entries if isinstance(entries, list) else []):
            if not isinstance(entry, dict):
                continue
            oid = str(entry.get(id_field) or f"{kind}_{index + 1}")
            owners.append((kind, oid, str(entry.get("title") or oid), entry, ""))

    stats = ctx.protagonist.get("stats")
    actions = stats.get("special_actions") if isinstance(stats, dict) else None
    for action in actions if isinstance(actions, list) else []:
        if isinstance(action, dict) and action.get("is_locked"):
            aid = str(action.get("id") or "?")
            title = str(action.get("name") or aid)
            owners.append(("special_action", aid, title, action, _SPECIAL_ACTION_PREFIX))

    for npc in ctx.entities_of("NPC"):
        trigger = metadata(npc).get("attack_trigger")
        if isinstance(trigger, dict):
            nid = entity_id(npc) or "?"
            owners.append(("npc_attack_trigger", nid, f"Attack trigger of {nid}", trigger, ""))
    return owners


def _owner_location(kind: str, oid: str) -> str:
    if kind == "special_action":
        return "protagonist"
    if kind == "npc_attack_trigger":
        return f"entity:{oid}"
    return f"{kind}:{oid}"


def check_hard_rule_references(ctx: ValidationContext) -> list[ValidationFinding]:
    """Sequences, quests, awards, special-action unlocks, and NPC attack triggers
    can only fire when their required item/scene/NPC exists."""
    findings: list[ValidationFinding] = []
    for kind, oid, title, rule, prefix in _rule_owners(ctx):
        for field, (ref_kind, ids_attr) in _HARD_RULE_FIELDS.items():
            target = str(rule.get(prefix + field) or "").strip()
            if not target or target in getattr(ctx, ids_attr):
                continue
            label = kind.replace("_", " ").capitalize()
            findings.append(
                finding(
                    "error",
                    f"{kind}_references_missing_{ref_kind}",
                    f"{label} '{title}' {_RULE_VERBS[ref_kind]} '{target}' which does not exist.",
                    location=_owner_location(kind, oid),
                    **{f"{kind}_id": oid, field: target},
                )
            )
    return findings
