"""Field allowlists and target resolution for AI fix patches."""

import logging
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.editing.ai_fix_soft_rules import parse_soft_rule_key
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene

logger = logging.getLogger(__name__)


_FIX_PROTAGONIST_FIELDS = frozenset(
    {
        "name",
        "description",
        "goal",
        "character",
        "hp",
        "mana",
        "stamina",
        "strength",
        "intelligence",
        "wisdom",
        "dexterity",
        "charisma",
        "armor_class",
        "exp",
        "on_hp_change_script",
        "on_hp_change_text",
        "on_status_change_script",
        "on_status_change_text",
    }
)

_FIX_ADVENTURE_FIELDS = frozenset(
    {
        "title",
        "teaser",
        "plot",
        "rules",
        "intro_text",
        "tts_director_notes",
        "completed_condition",
        "gameover_condition",
    }
)

_FIX_SCENE_FIELDS = frozenset(
    {
        "label",
        "description",
        "decorative_objects",
        "on_enter_scene_script",
        "on_enter_scene_text",
        "on_leave_scene_script",
        "on_leave_scene_text",
        "helpers_script",
    }
)

_FIX_EXIT_FIELDS = frozenset(
    {
        "label",
        "lock_description",
        "exit_type",
        "locked",
        "code_to_unlock",
        "item_to_unlock",
        "rule_to_unlock",
        "unlock_expression",
        "on_open_exit_script",
        "on_open_exit_text",
        "on_exit_used_script",
        "on_exit_used_text",
        "on_unlock_success_script",
        "on_unlock_success_text",
        "on_unlock_failure_script",
        "on_unlock_failure_text",
    }
)

_FIX_NPC_FIELDS = frozenset(
    {
        "name",
        "description",
        "goal",
        "character",
        "is_killable",
        "current_scene_id",
        "is_hidden",
        "reveal_rule",
        "spatial_position",
    }
)

_FIX_OBJECT_FIELDS = frozenset(
    {
        "name",
        "description",
        "is_portable",
        "current_scene_id",
        "locked",
        "code_to_unlock",
        "item_to_unlock",
        "rule_to_unlock",
        "unlock_expression",
        "on_unlock_success_script",
        "on_unlock_success_text",
        "on_unlock_failure_script",
        "on_unlock_failure_text",
        "text_log_content",
        "text_log_format",
        "on_read_script",
        "on_read_text",
        "craft_guard_expression",
        "on_craft_success_script",
        "on_craft_success_text",
        "on_craft_failure_script",
        "on_craft_failure_text",
        "is_hidden",
        "reveal_rule",
        "spatial_position",
    }
)


_FIX_SEQUENCE_FIELDS = frozenset(
    {
        "title",
        "description",
        "walkthrough",
        "end_condition",
        "required_item_id",
        "required_scene_id",
        "required_defeated_npc_id",
        "guard_expression",
        "completion_guard_expression",
        "on_start_sequence_script",
        "on_start_sequence_text",
        "on_end_sequence_script",
        "on_end_sequence_text",
        "helpers_script",
    }
)


def is_allowed_field(target_type: str, field: str) -> bool:
    """Allowlist check; sequences also accept ``soft_rules.<RULE_ID>.<field>`` keys."""
    if field in _allowed_fields_for(target_type):
        return True
    return target_type == "sequence" and parse_soft_rule_key(field) is not None


def _allowed_fields_for(target_type: str) -> frozenset[str]:
    return {
        "scene": _FIX_SCENE_FIELDS,
        "exit": _FIX_EXIT_FIELDS,
        "npc": _FIX_NPC_FIELDS,
        "object": _FIX_OBJECT_FIELDS,
        "protagonist": _FIX_PROTAGONIST_FIELDS,
        "adventure": _FIX_ADVENTURE_FIELDS,
        "sequence": _FIX_SEQUENCE_FIELDS,
    }.get(target_type, frozenset())


def _normalize_field_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _normalize_field_value(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_normalize_field_value(v) for v in value]
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if value is None:
        return None
    return str(value)


def _exit_match_filters(raw: str) -> list[tuple[Any, ...]]:
    """Exit lookups from most to least specific (see ``_resolve_exit_target``)."""
    upper = raw.upper()
    filters: list[tuple[Any, ...]] = [(WorldExit.id == raw,)]
    if "->" in raw:
        left, right = raw.split("->", 1)
        filters.append(
            (
                WorldExit.from_scene_id == left.strip().upper(),
                WorldExit.to_scene_id == right.strip().upper(),
            )
        )
    filters += [
        (WorldExit.id == upper,),
        (WorldExit.from_scene_id == upper,),
        (WorldExit.to_scene_id == upper,),
    ]
    return filters


async def _resolve_exit_target(
    *,
    db: AsyncSession,
    template_id: str,
    raw_target_id: str,
) -> Optional[WorldExit]:
    """Resolve an exit target_id in multiple ways.

    The AI sometimes emits ``target_id`` as:
      * the exit's primary key UUID (e.g. ``019EFF1D-8885-...``)
      * the ``from_scene_id -> to_scene_id`` composite (``"A->B"``)
      * one of the two scene IDs alone
      * the exit's human-readable ``label`` (case-insensitive, unique)

    We try the most specific match first, then relax. This keeps the
    apply-fix resilient against stale cached proposals whose original
    UUID no longer exists, and against AI proposals that picked a more
    human-readable identifier.
    """
    raw = str(raw_target_id or "").strip()
    if not raw:
        return None

    for conditions in _exit_match_filters(raw):
        res = await db.execute(
            select(WorldExit).where(WorldExit.template_id == template_id, *conditions).limit(1)
        )
        match = res.scalars().first()
        if match is not None:
            return match

    label_ci = raw.lower()
    res = await db.execute(select(WorldExit).where(WorldExit.template_id == template_id))
    candidates = [
        row for row in res.scalars().all() if (row.label or "").strip().lower() == label_ci
    ]
    return candidates[0] if len(candidates) == 1 else None


async def _resolve_entity_target(
    *,
    db: AsyncSession,
    template_id: str,
    entity_type: str,
    raw_target_id: str,
) -> Optional[WorldEntity]:
    """Resolve a scene/object/npc target_id; matches by exact ID, label, or unique label."""
    raw = str(raw_target_id or "").strip()
    if not raw:
        return None

    upper = raw.upper()
    res = await db.execute(
        select(WorldEntity).where(
            WorldEntity.template_id == template_id,
            WorldEntity.session_id.is_(None),
            WorldEntity.id == upper,
        )
    )
    match = res.scalars().first()
    if match is not None and match.entity_type == entity_type.upper():
        return match

    if match is not None and match.entity_type != entity_type.upper():
        return None

    label_ci = raw.strip().lower()
    res = await db.execute(
        select(WorldEntity).where(
            WorldEntity.template_id == template_id,
            WorldEntity.session_id.is_(None),
            WorldEntity.entity_type == entity_type.upper(),
        )
    )
    candidates = []
    for row in res.scalars().all():
        if (row.name or "").strip().lower() == label_ci:
            candidates.append(row)
    if len(candidates) == 1:
        return candidates[0]

    return None


async def _resolve_scene_target(
    *,
    db: AsyncSession,
    template_id: str,
    raw_target_id: str,
) -> Optional[WorldScene]:
    """Resolve a scene target_id; matches by exact ID or unique label."""
    raw = str(raw_target_id or "").strip()
    if not raw:
        return None

    upper = raw.upper()
    res = await db.execute(
        select(WorldScene).where(
            WorldScene.template_id == template_id,
            WorldScene.session_id.is_(None),
            WorldScene.id == upper,
        )
    )
    match = res.scalars().first()
    if match is not None:
        return match

    label_ci = raw.strip().lower()
    res = await db.execute(
        select(WorldScene).where(
            WorldScene.template_id == template_id,
            WorldScene.session_id.is_(None),
        )
    )
    candidates = []
    for row in res.scalars().all():
        if (row.label or "").strip().lower() == label_ci:
            candidates.append(row)
    if len(candidates) == 1:
        return candidates[0]
    return None
