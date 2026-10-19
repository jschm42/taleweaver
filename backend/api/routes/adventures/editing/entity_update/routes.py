"""PATCH endpoint that updates one editor target (cover, protagonist, scene, exit, NPC, item)."""

from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.editing.common import _get_owned_adventure_or_404
from backend.api.routes.adventures.editing.entity_update.entity_common import (
    apply_common_fields,
    rename_entity,
)
from backend.api.routes.adventures.editing.entity_update.fields import given, template_rows
from backend.api.routes.adventures.editing.entity_update.item import update_item
from backend.api.routes.adventures.editing.entity_update.npc import update_npc
from backend.api.routes.adventures.editing.entity_update.protagonist import (
    update_cover,
    update_protagonist,
)
from backend.api.routes.adventures.editing.entity_update.scene_exit import (
    update_exit,
    update_scene,
)
from backend.api.routes.adventures.editing.schemas import EntityUpdateRequest
from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.models.world_entity import WorldEntity

router = APIRouter(tags=["Editor"])

_Handler = Callable[[AsyncSession, str, AdventureTemplate, EntityUpdateRequest], Awaitable[None]]


async def _update_world_entity(
    db: AsyncSession, template_id: str, adv: AdventureTemplate, payload: EntityUpdateRequest
) -> None:
    rows = await template_rows(db, WorldEntity, template_id, WorldEntity.id == payload.target_id)
    if not rows:
        return
    ent = rows[0]
    if given(payload, "new_id"):
        await rename_entity(db, template_id, ent, payload.new_id or "")
    apply_common_fields(ent, payload)
    if ent.entity_type == "NPC":
        await update_npc(db, template_id, ent, payload)
    if ent.entity_type == "OBJECT":
        await update_item(db, template_id, adv, ent, payload)


_HANDLERS: dict[str, _Handler] = {
    "cover": update_cover,
    "protagonist": update_protagonist,
    "scene": update_scene,
    "exit": update_exit,
    "npc": _update_world_entity,
    "object": _update_world_entity,
}


@router.patch("/{template_id}/editor/entity")
async def update_editor_entity(
    template_id: str,
    payload: EntityUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)
    await _HANDLERS[payload.target_type](db, template_id, adv, payload)
    await db.commit()
    return {"status": "success"}
