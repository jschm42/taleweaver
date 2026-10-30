"""World-Builder patches that create new NPCs and objects (``new_npc`` / ``new_object``).

Only the World-Builder may create entities; AI fix suggestions stay update-only. A create
patch carries the new id in ``target_id`` and the starting fields in ``field_updates``.
Anything beyond these fields is configured by a regular npc/object patch that follows it
in the same proposal.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.editing.common import OBJECT_ID_PATTERN
from backend.api.routes.adventures.editing.entity_create import create_template_entity
from backend.api.routes.adventures.editing.schemas import EntityCreateRequest
from backend.schemas.validation import FixProposalEntityPatch

# Create patch type -> entity type and the patch type whose length limits apply.
CREATE_TARGET_TYPES: dict[str, tuple[str, str]] = {
    "new_npc": ("NPC", "npc"),
    "new_object": ("OBJECT", "object"),
}

# Item types that need no structured configuration (switch states, recipes) to work.
CREATABLE_ITEM_TYPES = frozenset(
    {"DEFAULT", "CONSUMABLE", "READABLE", "WEARABLE", "WEAPON", "CONTAINER"}
)

_COMMON_FIELDS = frozenset(
    {"name", "description", "current_scene_id", "appearance", "is_hidden", "reveal_rule"}
)
_CREATE_FIELDS: dict[str, frozenset[str]] = {
    "new_npc": _COMMON_FIELDS | {"goal", "character", "is_killable", "hp"},
    "new_object": _COMMON_FIELDS | {"item_type", "is_portable"},
}
_REQUIRED_FIELDS = ("name", "description", "current_scene_id")


def is_create_type(target_type: str) -> bool:
    return target_type in CREATE_TARGET_TYPES


def limits_type(target_type: str) -> str:
    """The update patch type whose field length limits apply to ``target_type``."""
    return CREATE_TARGET_TYPES.get(target_type, ("", target_type))[1]


def is_allowed_create_field(target_type: str, field: str) -> bool:
    return field in _CREATE_FIELDS.get(target_type, frozenset())


def _known_ids(summary: dict[str, Any]) -> set[str]:
    return {
        str(entry.get("id") or "").strip().upper()
        for key in ("scenes", "npcs", "objects")
        for entry in summary.get(key) or []
    }


def _scene_ids(summary: dict[str, Any]) -> set[str]:
    return {str(s.get("id") or "").strip().upper() for s in summary.get("scenes") or []}


def creation_problems(
    target_type: str, target_id: str, updates: dict[str, Any], summary: dict[str, Any]
) -> list[str]:
    """Reasons a create patch cannot be applied (empty when it is fine)."""
    new_id = str(target_id or "").strip().upper()
    if not OBJECT_ID_PATTERN.match(new_id):
        return [f"{target_type} id '{target_id}' (use A-Z, 0-9 and _, max 30 chars)"]
    if new_id in _known_ids(summary):
        return [f"{target_type} id '{new_id}' already exists"]
    problems = [
        f"{target_type}.{name} is missing"
        for name in _REQUIRED_FIELDS
        if not str(updates.get(name) or "").strip()
    ]
    scene_id = str(updates.get("current_scene_id") or "").strip().upper()
    if scene_id and scene_id not in _scene_ids(summary):
        problems.append(f"{target_type} scene '{scene_id}' does not exist")
    item_type = str(updates.get("item_type") or "DEFAULT").strip().upper()
    if target_type == "new_object" and item_type not in CREATABLE_ITEM_TYPES:
        problems.append(f"new_object.item_type {item_type} cannot be created")
    return problems


def _create_request(patch: FixProposalEntityPatch) -> EntityCreateRequest:
    updates = patch.field_updates
    entity_type = CREATE_TARGET_TYPES[patch.target_type][0]
    is_object = entity_type == "OBJECT"
    return EntityCreateRequest(
        entity_id=str(patch.target_id or "").strip().upper(),
        entity_type=entity_type,  # type: ignore[arg-type]
        scene_id=str(updates.get("current_scene_id") or "").strip().upper(),
        name=str(updates.get("name") or "").strip(),
        description=str(updates.get("description") or "").strip(),
        appearance=str(updates.get("appearance") or "").strip()[:100] or None,
        item_type=str(updates.get("item_type") or "DEFAULT").upper() if is_object else None,
        is_portable=updates.get("is_portable") if is_object else None,
        goal=updates.get("goal"),
        character=updates.get("character"),
        is_killable=updates.get("is_killable"),
        hp=updates.get("hp"),
        is_hidden=updates.get("is_hidden"),
        reveal_rule=updates.get("reveal_rule"),
    )


async def apply_create_patch(
    db: AsyncSession, template_id: str, patch: FixProposalEntityPatch
) -> str:
    """Creates the entity of a create patch; returns its 'type:id' tag (HTTP 4xx on bad input)."""
    entity = await create_template_entity(db, template_id, _create_request(patch))
    await db.flush()
    return f"{patch.target_type}:{entity.id}"
