"""Editor endpoint for an NPC's combat profile: attributes, armor class and main attack."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.editor import _get_owned_adventure_or_404, _sanitize_editor_id
from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.engine.combat.npc_attack import (
    AC_COLUMN,
    ATTACK_DICE_RX,
    MAX_ATTACK_NAME,
    NPC_STAT_COLUMNS,
    armor_class_column,
    normalize_main_attack,
)
from backend.engine.combat.special_attacks import normalize_effects
from backend.engine.combat.weapons import MAX_WEAPON_EFFECTS
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.models.world_entity import WorldEntity

router = APIRouter(tags=["Editor"])

StatName = Literal["strength", "dexterity", "intelligence", "wisdom", "charisma"]
MIN_STAT, MAX_STAT = 1, 30
MIN_AC, MAX_AC = 1, 40


class MainAttackPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=MAX_ATTACK_NAME)
    category: Literal["MELEE", "RANGED", "MAGIC"] = "MELEE"
    damage_dice: str = Field("1d6", max_length=20)
    hit_stat: StatName = "dexterity"
    cost_type: Literal["stamina", "mana"] = "stamina"
    cost: int = Field(default=0, ge=0, le=999)
    effects: list[dict[str, Any]] = Field(default_factory=list, max_length=MAX_WEAPON_EFFECTS)


class NpcProfileUpdateRequest(BaseModel):
    npc_id: str
    strength: int = Field(default=10, ge=MIN_STAT, le=MAX_STAT)
    dexterity: int = Field(default=10, ge=MIN_STAT, le=MAX_STAT)
    intelligence: int = Field(default=10, ge=MIN_STAT, le=MAX_STAT)
    wisdom: int = Field(default=10, ge=MIN_STAT, le=MAX_STAT)
    charisma: int = Field(default=10, ge=MIN_STAT, le=MAX_STAT)
    armor_class: int = Field(default=10, ge=MIN_AC, le=MAX_AC)
    main_attack: Optional[MainAttackPayload] = None


def _clean_main_attack(payload: Optional[MainAttackPayload]) -> dict[str, Any] | None:
    if payload is None:
        return None
    dice = payload.damage_dice.replace(" ", "").lower()
    if not ATTACK_DICE_RX.match(dice):
        raise HTTPException(
            status_code=400, detail="main_attack.damage_dice: use e.g. 1d8 or 2d6+1."
        )
    effects = normalize_effects(payload.effects)
    if len(effects) != len(payload.effects):
        raise HTTPException(
            status_code=400,
            detail="main_attack.effects: every effect needs target, stat and an amount like -1d4.",
        )
    return normalize_main_attack({**payload.model_dump(), "damage_dice": dice, "effects": effects})


def _update_manifest(adv: AdventureTemplate, npc_id: str, values: dict[str, Any]) -> None:
    if not isinstance(adv.original_manifest, dict):
        return
    manifest = deepcopy(adv.original_manifest)
    for npc in manifest.get("npcs") or []:
        if isinstance(npc, dict) and npc.get("id") == npc_id:
            npc.update(values)
    adv.original_manifest = manifest
    flag_modified(adv, "original_manifest")


async def _load_npc(db: AsyncSession, template_id: str, npc_id: str) -> WorldEntity:
    res = await db.execute(
        select(WorldEntity).where(
            WorldEntity.template_id == template_id,
            WorldEntity.session_id.is_(None),
            WorldEntity.entity_type == "NPC",
            WorldEntity.id == npc_id,
        )
    )
    npc = res.scalars().first()
    if not npc:
        raise HTTPException(status_code=404, detail="NPC not found")
    return npc


@router.put("/{template_id}/editor/npc-profile")
async def update_npc_profile(
    template_id: str,
    payload: NpcProfileUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Stores the NPC's attributes, armor class and configurable main attack."""
    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)
    npc_id = _sanitize_editor_id(payload.npc_id, "npc_id")
    npc = await _load_npc(db, template_id, npc_id)
    main_attack = _clean_main_attack(payload.main_attack)

    stats = {key: getattr(payload, key) for key in NPC_STAT_COLUMNS}
    columns = {column: stats[key] for key, column in NPC_STAT_COLUMNS.items()}
    columns[AC_COLUMN] = armor_class_column(payload.armor_class)
    for column, value in columns.items():
        setattr(npc, column, value)
    npc.metadata_json = {**(npc.metadata_json or {}), "main_attack": main_attack}
    flag_modified(npc, "metadata_json")

    _update_manifest(
        adv,
        npc_id,
        {**stats, "armor_class": payload.armor_class, **columns, "main_attack": main_attack},
    )
    await db.commit()
    return {
        "status": "success",
        **stats,
        "armor_class": payload.armor_class,
        "main_attack": main_attack,
    }
