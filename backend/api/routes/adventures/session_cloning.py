"""Row cloning shared by "start a session" and "copy a session"."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Optional

from backend.engine.rules.item_logic import normalize_equipment_keys
from backend.engine.world.scene_fields import scene_content
from backend.models.avatar import Avatar
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene

_AVATAR_FIELDS = (
    "name",
    "role",
    "description",
    "profile_image",
    "voice",
    "hp",
    "max_hp",
    "stamina",
    "max_stamina",
    "mana",
    "max_mana",
    "strength",
    "dexterity",
    "intelligence",
    "wisdom",
    "charisma",
    "armor_class",
)
_EXIT_FIELDS = (
    "from_scene_id",
    "to_scene_id",
    "label",
    "exit_type",
    "is_locked",
    "lock_description",
    "code_to_unlock",
    "item_to_unlock",
    "rule_to_unlock",
)
_ENTITY_FIELDS = (
    "id",
    "entity_type",
    "name",
    "description",
    "current_scene_id",
    "spatial_position",
    "item_type",
    "wearable_slots",
    "is_hidden",
    "is_portable",
    "combination_ingredients",
    "reveals_item_id",
    "is_final_state",
    "state_comment",
    "npc_type",
    "movement_type",
    "notes",
    "hp",
    "max_hp",
    "mana",
    "max_mana",
    "stamina",
    "max_stamina",
    "stat_modifier_strength",
    "stat_modifier_dexterity",
    "stat_modifier_intelligence",
    "stat_modifier_wisdom",
    "stat_modifier_charisma",
    "stat_modifier_armor_class",
    "is_attackable",
    "is_killable",
)


def clone_avatar(source: Avatar, user_id: str, template_id: Optional[str]) -> Avatar:
    return Avatar(
        user_id=user_id,
        template_id=template_id,
        **{field: getattr(source, field) for field in _AVATAR_FIELDS},
        stats=deepcopy(source.stats or {}),
        inventory=deepcopy(source.inventory or []),
        equipment=normalize_equipment_keys(source.equipment),
        status_effects=deepcopy(source.status_effects or []),
    )


def clone_scene(scene: WorldScene, session_id: str, image_url: Optional[str]) -> WorldScene:
    return WorldScene(
        **scene_content(scene),
        session_id=session_id,
        template_id=None,
        image_url=image_url or scene.image_url,
    )


def clone_exit(exit_row: WorldExit, session_id: str) -> WorldExit:
    return WorldExit(
        session_id=session_id,
        template_id=None,
        **{field: getattr(exit_row, field) for field in _EXIT_FIELDS},
    )


def _is_moveable(entity: WorldEntity) -> bool:
    if entity.moveable is not None:
        return bool(entity.moveable)
    return str(entity.movement_type or "").upper() == "MOVABLE"


def clone_entity(
    entity: WorldEntity, session_id: str, image_url: Optional[str], **overrides: Any
) -> WorldEntity:
    """Session copy of an entity; ``overrides`` set fields that differ per caller."""
    values: dict[str, Any] = {field: getattr(entity, field) for field in _ENTITY_FIELDS}
    values.update(
        session_id=session_id,
        template_id=None,
        image_url=image_url or entity.image_url,
        moveable=_is_moveable(entity),
        allowed_scenes=deepcopy(entity.allowed_scenes) if entity.allowed_scenes else [],
        inventory=deepcopy(entity.inventory),
        metadata_json=deepcopy(entity.metadata_json),
    )
    values.update(overrides)
    return WorldEntity(**values)
