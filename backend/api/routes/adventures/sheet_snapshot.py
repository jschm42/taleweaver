"""Builds the serialisable character-sheet snapshot sent to the game UI."""

from __future__ import annotations

import os
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.asset_url_healing import (
    heal_template_avatar_profile_image,
    resolve_existing_data_asset_url,
)
from backend.api.routes.adventures.session_adventure import (
    SessionAdventure,
    load_session_adventure,
)
from backend.api.routes.adventures.session_start_settings import resolve_start_datetime
from backend.core.config import settings
from backend.core.narration_styles import DEFAULT_NARRATION_STYLE
from backend.core.ui_theme import UI_SKIN_AUTO, normalize_ui_theme
from backend.engine.item_logic import get_item_slot, normalize_equipment_keys
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldEntity, WorldScene
from backend.utils.path_security import data_url_to_local_path

_FALLBACK_CLOCK_START = "2026-04-17T08:00:00"
_PROFILE_IMAGE_CANDIDATES = 10
_STAT_KEYS = ("strength", "dexterity", "intelligence", "wisdom", "charisma", "armor_class")
_STAT_MODIFIERS = tuple(f"stat_modifier_{key}" for key in _STAT_KEYS)
# Agent flag in the sheet -> (key in entity_states["__agent__"], default).
_AGENT_FLAGS = {
    "agent_active": ("active", False),
    "agent_monkey_mode": ("monkey_mode", False),
    "agent_allow_walkthrough": ("allow_walkthrough", True),
    "agent_step_by_step": ("step_by_step", False),
}


def _as_int(*candidates: Any) -> Optional[int]:
    for candidate in candidates:
        if candidate is None:
            continue
        try:
            return int(candidate)
        except (TypeError, ValueError):
            continue
    return None


def _as_str(*candidates: Any) -> Optional[str]:
    return next((c.strip() for c in candidates if isinstance(c, str) and c.strip()), None)


def _entity_slot(entity: WorldEntity) -> Any:
    wearable = entity.wearable_slots
    if isinstance(wearable, list) and wearable:
        return wearable[0]
    if isinstance(wearable, str):
        return wearable
    return get_item_slot(entity.name or "", entity.item_type or "PICKABLE")


def entity_to_item_dict(entity: WorldEntity) -> dict:
    """Minimal item dict from a WorldEntity for character sheet display."""
    metadata = entity.metadata_json or {}
    effects = metadata.get("effects") if isinstance(metadata.get("effects"), dict) else {}
    return {
        "id": entity.id,
        "name": entity.name,
        "description": entity.description,
        "image_url": entity.image_url,
        "item_type": entity.item_type or "PICKABLE",
        "slot": _entity_slot(entity),
        "metadata_json": dict(metadata),
        **{field: _as_int(getattr(entity, field)) for field in _STAT_MODIFIERS},
        "hp_change": _as_int(metadata.get("hp_change"), effects.get("hp")),
        "stamina_change": _as_int(metadata.get("stamina_change"), effects.get("stamina")),
        "mana_change": _as_int(metadata.get("mana_change"), effects.get("mana")),
        "damage_dice": _as_str(metadata.get("damage_dice")),
        "weapon_cost_type": _as_str(metadata.get("weapon_cost_type")),
        "weapon_cost_value": _as_int(metadata.get("weapon_cost_value")),
    }


class _SheetContext:
    """The session's own adventure copy with a fallback to the raw manifest snapshot."""

    def __init__(
        self,
        adventure: Optional[SessionAdventure],
        snapshot_adventure: dict[str, Any],
        manifest: dict[str, Any],
    ) -> None:
        self.adventure = adventure
        self.snapshot_adventure = snapshot_adventure
        self.manifest = manifest

    def get(self, key: str, default: Any = None) -> Any:
        if self.adventure:
            return getattr(self.adventure, key)
        return self.snapshot_adventure.get(key, default)

    def template_value(self, key: str, default: Any = None) -> Any:
        """Only the session adventure's value (no raw snapshot fallback)."""
        return getattr(self.adventure, key) if self.adventure else default


async def _start_datetime(state: SessionState, ctx: _SheetContext) -> Optional[str]:
    time_config = ctx.get("time_config")
    manifest = ctx.adventure.original_manifest if ctx.adventure else ctx.manifest
    start = resolve_start_datetime(manifest, state=state, time_config=time_config)
    clock_enabled = ctx.template_value("clock_enabled") or ctx.snapshot_adventure.get(
        "clock_enabled"
    )
    if start or not clock_enabled:
        return start
    resolved = resolve_start_datetime({"time_config": time_config or {}}, time_config=time_config)
    return resolved or _FALLBACK_CLOCK_START


def _string_images(images: Any) -> dict[str, str]:
    return {k: v for k, v in (images or {}).items() if isinstance(v, str) and v}


async def _entity_image_map(db: AsyncSession, state: SessionState, snapshot: dict) -> dict:
    snapshot_images = _string_images(snapshot.get("entity_images"))
    if "__asset_snapshot__" in (state.entity_states or {}):
        return snapshot_images
    res = await db.execute(
        select(WorldEntity.id, WorldEntity.image_url).where(
            WorldEntity.session_id == state.session_id, WorldEntity.image_url.is_not(None)
        )
    )
    image_map = {row.id: row.image_url for row in res.all() if row.id}
    image_map.update(snapshot_images)
    return image_map


async def _item_entities(db: AsyncSession, avatar: Avatar, session_id: str) -> dict[str, Any]:
    """Entities for items stored as bare IDs (legacy format); session rows win over template rows."""
    equipment = normalize_equipment_keys(avatar.equipment).values()
    ids = {i for i in [*(avatar.inventory or []), *equipment] if isinstance(i, str) and i}
    if not ids:
        return {}
    lookup: dict[str, Any] = {}
    result = await db.execute(select(WorldEntity).where(WorldEntity.id.in_(ids)))
    for ent in result.scalars().all():
        if ent.id not in lookup or ent.session_id == session_id:
            lookup[ent.id] = ent
    return lookup


def _sheet_item(item: dict, image_map: dict[str, str]) -> dict:
    item_copy = dict(item)
    if not item_copy.get("slot"):
        item_copy["slot"] = get_item_slot(
            item_copy.get("name", ""), item_copy.get("item_type", "PICKABLE")
        )
    item_id = item_copy.get("id")
    if item_id in image_map and not item_copy.get("image_url"):
        item_copy["image_url"] = image_map[item_id]
    return item_copy


def _expand(item: Any, entity_lookup: dict[str, Any]) -> Any:
    if not isinstance(item, str):
        return item
    entity = entity_lookup.get(item)
    return entity_to_item_dict(entity) if entity else {"name": item}


def _sync_inventory(avatar: Avatar, entity_lookup: dict, image_map: dict) -> list[dict]:
    expanded = (_expand(item, entity_lookup) for item in (avatar.inventory or []))
    return [_sheet_item(item, image_map) for item in expanded if isinstance(item, dict)]


def _sync_equipment(avatar: Avatar, entity_lookup: dict, image_map: dict) -> dict[str, Any]:
    synced: dict[str, Any] = {}
    for slot, raw_item in normalize_equipment_keys(avatar.equipment).items():
        item = _expand(raw_item, entity_lookup) if raw_item else raw_item
        synced[slot] = _sheet_item(item, image_map) if isinstance(item, dict) and item else item
    return synced


async def _current_scene(db: AsyncSession, state: SessionState) -> Optional[WorldScene]:
    for owner_filter in (
        WorldScene.session_id == state.session_id,
        WorldScene.template_id == state.template_id,
    ):
        res = await db.execute(
            select(WorldScene).where(WorldScene.id == state.current_scene_id, owner_filter)
        )
        scene = res.scalars().first()
        if scene:
            return scene
    return None


async def _template_avatar_image(db: AsyncSession, template_id: str) -> Optional[str]:
    result = await db.execute(
        select(Avatar.profile_image)
        .where(
            Avatar.template_id == template_id,
            Avatar.profile_image.is_not(None),
            Avatar.profile_image != "",
        )
        .order_by(Avatar.updated_at.desc())
        .limit(_PROFILE_IMAGE_CANDIDATES)
    )
    resolved = (resolve_existing_data_asset_url(c) for c in result.scalars().all())
    return next((url for url in resolved if url), None)


async def _profile_image(
    db: AsyncSession, state: SessionState, manifest: dict, session_image: Any
) -> Optional[str]:
    """Session asset, healed library image, manifest protagonist image, then template avatars."""
    image = session_image
    if image and "/adventures/sessions/" in image:
        abs_path = data_url_to_local_path(image)
        if not abs_path or not os.path.isfile(abs_path):
            image = heal_template_avatar_profile_image(state.template_id, image)
    if not image:
        protagonist = manifest.get("protagonist") if isinstance(manifest, dict) else None
        if isinstance(protagonist, dict):
            image = resolve_existing_data_asset_url(protagonist.get("profile_image"))
    if not image and state.template_id:
        image = await _template_avatar_image(db, state.template_id)
    return image


def _agent_fields(state: SessionState) -> dict[str, Any]:
    agent = (state.entity_states or {}).get("__agent__", {})
    fields: dict[str, Any] = {
        name: bool(agent.get(key, default)) for name, (key, default) in _AGENT_FLAGS.items()
    }
    fields["agent_personality"] = str(agent.get("personality", "casual"))
    fields["agent_custom_personality"] = str(agent.get("custom_personality", ""))
    return fields


def _memory_turns(state: SessionState, adventure: Optional[AdventureTemplate]) -> Any:
    turns = getattr(state, "max_memory_turns", None)
    if turns is not None:
        return turns
    return getattr(adventure, "max_memory_turns", 10) if adventure else 10


def _adventure_fields(state: SessionState, ctx: _SheetContext) -> dict[str, Any]:
    return {
        "adventure_title": ctx.template_value("title", "Unknown"),
        "adventure_version": ctx.template_value("version"),
        "creator": ctx.template_value("creator"),
        "copyright": ctx.template_value("copyright"),
        "license": ctx.template_value("license"),
        "license_url": ctx.template_value("license_url"),
        "template_id": state.template_id,
        "rule_enforcement_mode": ctx.get("rule_enforcement_mode", "rpg"),
        "adventure_tone": ctx.get("selected_tone"),
        "ui_theme": normalize_ui_theme(ctx.get("ui_theme")),
        "clock_enabled": bool(ctx.get("clock_enabled", False)),
        "time_system": state.time_system or ctx.get("time_system", "relative"),
        "time_config": state.time_config or ctx.get("time_config"),
        "time_per_turn": ctx.get("time_per_turn", 5),
        "max_time_per_turn": ctx.get("max_time_per_turn"),
        "max_memory_turns": _memory_turns(state, ctx.adventure),
    }


def _avatar_fields(avatar: Avatar, total_stats: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": avatar.name,
        "role": avatar.role,
        "description": avatar.description,
        "hp": avatar.hp,
        "max_hp": avatar.max_hp,
        "stamina": avatar.stamina,
        "max_stamina": avatar.max_stamina,
        "mana": avatar.mana,
        "max_mana": avatar.max_mana,
        **{key: total_stats.get(key, getattr(avatar, key)) for key in _STAT_KEYS},
        "stats": total_stats,
        "status_effects": avatar.status_effects or [],
        "special_actions": avatar.stats.get("special_actions") or [],
        "unlocked_actions": avatar.stats.get("unlocked_actions") or [],
        "exp": avatar.exp,
    }


async def build_sheet_snapshot(
    avatar: Avatar,
    state: SessionState,
    db: AsyncSession,
    manifest_snapshot: dict[str, Any],
    session_manifest: dict[str, Any],
    asset_snapshot: dict[str, Any],
    session_profile_image: Optional[str],
) -> dict:
    """Builds a serialisable character-sheet snapshot."""
    from backend.engine.stat_aggregator import calculate_total_stats

    ctx = _SheetContext(
        await load_session_adventure(db, state),
        manifest_snapshot.get("adventure") or {},
        session_manifest,
    )
    image_map = await _entity_image_map(db, state, asset_snapshot)
    entity_lookup = await _item_entities(db, avatar, state.session_id)
    current_scene = await _current_scene(db, state)
    return {
        **_avatar_fields(avatar, calculate_total_stats(avatar)),
        "profile_image": await _profile_image(db, state, session_manifest, session_profile_image),
        "inventory": _sync_inventory(avatar, entity_lookup, image_map),
        "equipment": _sync_equipment(avatar, entity_lookup, image_map),
        "in_game_time": state.in_game_time,
        "start_datetime": await _start_datetime(state, ctx),
        "current_scene": current_scene.label if current_scene else state.current_scene_id,
        "scene_id": state.current_scene_id,
        **_adventure_fields(state, ctx),
        "enable_history_compression": bool(getattr(state, "enable_history_compression", True)),
        "narration_style": getattr(state, "narration_style", None) or DEFAULT_NARRATION_STYLE,
        "ui_skin": getattr(state, "ui_skin", None) or UI_SKIN_AUTO,
        "compressed_history": getattr(state, "compressed_history", None),
        **_agent_fields(state),
        "is_debug_enabled": bool(state.is_debug_enabled),
        "debug_mode": bool(settings.TALEWEAVER_DEBUG_ENABLED or state.is_debug_enabled),
    }
