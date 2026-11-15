"""Per-room zone overrides derived from a Dynamic Cluster Blueprint.

When a dynamic cluster is entered, one blueprint plans every room. Each room's
``dynamic_zone`` then carries its own sub-theme and generation instructions, so the
scene generator follows the mini-adventure's thread instead of the zone-wide prompt.
The author's zone-wide values stay available as ``root_theme`` / ``root_instructions``.
"""

from __future__ import annotations

from typing import Any

from backend.engine.blueprint.parser import has_blueprint_tags
from backend.engine.world.dynamic_scene_schemas import normalize_instructions_scope

CLUSTER_INSTRUCTIONS_SOURCE = "cluster_blueprint"

_ROLE_INSTRUCTIONS: dict[str, str] = {
    "entry": (
        "Entrance room: set the mood and plant clues (tracks, notes, remains) that point to "
        "the threat deeper inside. At most a light first encounter; offer light supplies."
    ),
    "branch": (
        "Optional side room: quieter than the main route. Reward exploration with lore about "
        "the climax and a useful consumable or weapon; any NPC here is neutral or wary."
    ),
    "obstacle": (
        "Defended choke point on the main route: hostile resistance blocks the way. One hostile "
        "carries the zone key item that opens the reward at the climax."
    ),
    "climax": (
        "Climax room: the main guardian or mystery of this cluster waits here, together with a "
        "reward container that the zone key item from an earlier room opens."
    ),
}


def root_instructions_text(zone: dict[str, Any]) -> str:
    """Return the author's zone-wide instructions, even after a node override."""
    if zone.get("instructions_source") == CLUSTER_INSTRUCTIONS_SOURCE:
        return str(zone.get("root_instructions") or "").strip()
    return str(zone.get("instructions") or "").strip()


def root_instructions_scope(zone: dict[str, Any]) -> str:
    """Return the author's instruction scope, even after a node override."""
    if zone.get("instructions_source") == CLUSTER_INSTRUCTIONS_SOURCE:
        return normalize_instructions_scope(zone.get("root_instructions_scope"))
    return normalize_instructions_scope(zone.get("instructions_scope"))


def author_scope_applies(scope: str, depth: int, max_depth: int) -> bool:
    """Return whether author instructions with ``scope`` apply to a room at ``depth``."""
    if scope == "all_scenes":
        return True
    if scope == "max_depth":
        return depth >= max_depth
    return depth <= 1


def describe_author_scope(scope: str) -> str:
    """Explain an instruction scope in words for the blueprint architect prompt."""
    return {
        "all_scenes": "any room",
        "max_depth": "only the deepest (final) room",
        "first_scene": "only the entry room (D1_1)",
    }.get(scope, "once in the cluster, in the entry room (D1_1)")


def fallback_generation_instructions(
    role: str,
    depth: int,
    zone: dict[str, Any],
) -> str:
    """Build deterministic per-room instructions when no LLM blueprint is available."""
    parts = [_ROLE_INSTRUCTIONS.get(role, _ROLE_INSTRUCTIONS["obstacle"])]
    author_text = root_instructions_text(zone)
    max_depth = int(zone.get("max_depth") or 3)
    scope = root_instructions_scope(zone)
    if not author_text or has_blueprint_tags(author_text):
        return "\n".join(parts)[:1500]
    if author_scope_applies(scope, depth, max_depth):
        parts.append(author_text)
    else:
        parts.append(
            "Cluster premise (story context only; do not spawn the characters or items it "
            f"names in this room): {author_text}"
        )
    return "\n".join(parts)[:1500]


def restore_root_zone(zone: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``zone`` with node overrides replaced by the author's values."""
    restored = dict(zone)
    if restored.pop("instructions_source", None) == CLUSTER_INSTRUCTIONS_SOURCE:
        restored["instructions"] = restored.pop("root_instructions", None)
        restored["instructions_scope"] = normalize_instructions_scope(
            restored.pop("root_instructions_scope", None)
        )
    restored.pop("root_instructions", None)
    restored.pop("root_instructions_scope", None)
    if restored.get("root_theme"):
        restored["theme"] = restored["root_theme"]
    return restored


def apply_cluster_node_to_zone(zone: dict[str, Any], node_ctx: dict[str, Any]) -> dict[str, Any]:
    """Give ``zone`` the room's own theme and generation instructions (mutates and returns it).

    Loose author instructions were already folded into the blueprint, so the room's
    instructions replace them. Structured blueprint-tag instructions stay in place,
    because they are filtered per depth; the room's instructions then reach the
    generator through the cluster blueprint prompt section.
    """
    zone["cluster_node"] = node_ctx
    if not node_ctx:
        return zone
    zone["root_theme"] = zone.get("root_theme") or zone.get("theme")
    theme_hint = str(node_ctx.get("theme_hint") or "").strip()
    if theme_hint:
        zone["theme"] = theme_hint[:1000]

    node_instructions = str(node_ctx.get("generation_instructions") or "").strip()
    author_text = root_instructions_text(zone)
    if not node_instructions or has_blueprint_tags(author_text):
        return zone
    if zone.get("instructions_source") != CLUSTER_INSTRUCTIONS_SOURCE:
        zone["root_instructions"] = author_text or None
        zone["root_instructions_scope"] = normalize_instructions_scope(
            zone.get("instructions_scope")
        )
    zone["instructions"] = node_instructions[:8000]
    zone["instructions_scope"] = "all_scenes"
    zone["instructions_source"] = CLUSTER_INSTRUCTIONS_SOURCE
    zone["instructions_consumed"] = False
    return zone


_BRIEF_ITEM_TYPES: list[str] = [
    "STANDARD",
    "CONSUMABLE",
    "WEARABLE",
    "WEAPON",
    "READABLE",
    "CONTAINER",
    "SWITCH",
]


def is_room_brief_only(zone: dict[str, Any]) -> bool:
    """True when the zone's instructions are a room brief and the author text does not apply here."""
    if zone.get("instructions_source") != CLUSTER_INSTRUCTIONS_SOURCE:
        return False
    if not root_instructions_text(zone):
        return True
    depth = int(zone.get("depth") or 1)
    max_depth = int(zone.get("max_depth") or 3)
    return not author_scope_applies(root_instructions_scope(zone), depth, max_depth)


def adjust_plan_for_room_brief(plan: dict[str, Any]) -> dict[str, Any]:
    """Open item types for a room brief while keeping the rolled NPC and object counts.

    The architect already planned the room against the spawn chances, so the brief
    decides which kinds of objects appear; the counts stay as rolled (at least 1 object).
    """
    updated = dict(plan)
    updated["has_instructions"] = True
    updated["allow_items"] = True
    updated["allow_container"] = True
    updated["allow_switch"] = True
    updated["allowed_item_types"] = list(_BRIEF_ITEM_TYPES)
    updated["target_objects"] = max(1, int(updated.get("target_objects") or 0))
    return updated
