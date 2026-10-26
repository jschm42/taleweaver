"""Unified debug inspector payload for an active game session (/session-debug)."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene

logger = logging.getLogger(__name__)

# (resource, default) pairs shown for NPCs when neither override nor template sets them.
_NPC_RESOURCE_DEFAULTS = (
    ("hp", 100),
    ("max_hp", 100),
    ("stamina", 50),
    ("max_stamina", 50),
    ("mana", 50),
    ("max_mana", 50),
)
_STAT_FIELDS = ("strength", "dexterity", "intelligence", "wisdom", "charisma", "armor_class")


def _session_or_template(model: Any, state: SessionState):
    """Rows of the session plus the template rows not shadowed by a session copy."""
    return or_(
        model.session_id == state.session_id,
        and_(model.template_id == state.template_id, model.session_id.is_(None)),
    )


def _prefer_session_rows(rows: list[Any], key_fn, session_id: str) -> dict[str, Any]:
    lookup: dict[str, Any] = {}
    for row in rows:
        key = key_fn(row)
        if key not in lookup or row.session_id == session_id:
            lookup[key] = row
    return lookup


def _entity_scene_id(ent: WorldEntity, override: dict[str, Any]) -> str:
    return (
        override.get("current_scene_id")
        or getattr(ent, "current_scene_id", None)
        or getattr(ent, "start_scene_id", None)
        or "UNKNOWN"
    )


def _npc_resource(ent: WorldEntity, override: dict[str, Any], field: str, default: int) -> Any:
    template_value = getattr(ent, field, None)
    return override.get(field, template_value if template_value is not None else default)


def _npc_is_moveable(ent: WorldEntity, override: dict[str, Any]) -> bool:
    if override.get("moveable") is not None:
        return bool(override.get("moveable"))
    if getattr(ent, "moveable", None) is not None:
        return bool(ent.moveable)
    return str(getattr(ent, "movement_type", "") or "").upper() == "MOVABLE"


def _npc_role(ent: WorldEntity) -> str:
    return (
        getattr(ent, "role", None)
        or getattr(ent, "npc_type", None)
        or (getattr(ent, "metadata_json", None) or {}).get("role")
        or "NPC"
    )


def _build_npc_info(
    ent: WorldEntity, override: dict[str, Any], scene_names: dict[str, str], current_scene_id: str
) -> dict[str, Any]:
    loc_id = _entity_scene_id(ent, override)
    resources = {
        field: _npc_resource(ent, override, field, default)
        for field, default in _NPC_RESOURCE_DEFAULTS
    }
    is_defeated = bool(override.get("is_defeated", False))
    return {
        "id": ent.id,
        "name": ent.name,
        "description": getattr(ent, "description", "") or "",
        "role": _npc_role(ent),
        "image_url": getattr(ent, "image_url", None),
        "voice": getattr(ent, "voice", None),
        "current_scene_id": loc_id,
        "current_scene_name": scene_names.get(loc_id, loc_id),
        "start_scene_id": getattr(ent, "start_scene_id", None)
        or getattr(ent, "current_scene_id", "UNKNOWN"),
        **resources,
        "is_alive": not is_defeated and resources["hp"] > 0,
        "is_defeated": is_defeated,
        "is_hidden": bool(override.get("is_hidden", getattr(ent, "is_hidden", False))),
        "is_hostile": bool(override.get("is_hostile", getattr(ent, "is_hostile", False))),
        "inventory": override.get("inventory", getattr(ent, "inventory", None) or []),
        "notes": override.get("notes") or getattr(ent, "notes", None) or "",
        "moveable": _npc_is_moveable(ent, override),
        "allowed_scenes": override.get("allowed_scenes")
        or getattr(ent, "allowed_scenes", None)
        or [],
        "is_in_current_scene": loc_id == current_scene_id,
        "stats": {stat: getattr(ent, f"stat_modifier_{stat}", 0) or 10 for stat in _STAT_FIELDS},
    }


def _scene_npc_summary(npc: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "id",
        "name",
        "image_url",
        "hp",
        "max_hp",
        "is_alive",
        "is_hidden",
        "notes",
        "moveable",
        "allowed_scenes",
    )
    return {key: npc[key] for key in keys}


def _carried_item(
    itm: dict[str, Any], location_type: str, location_id: str, location_name: str, is_hidden: bool
) -> dict[str, Any]:
    """Item carried by the avatar, inside a container, or in an NPC inventory."""
    return {
        "id": itm.get("id") or itm.get("key") or itm.get("name"),
        "name": itm.get("name") or "Unnamed Item",
        "description": itm.get("description") or "",
        "item_type": itm.get("item_type") or "PICKABLE",
        "slot": itm.get("slot"),
        "image_url": itm.get("image_url"),
        "location_type": location_type,
        "location_id": location_id,
        "location_name": location_name,
        "is_hidden": is_hidden,
        "is_portable": True,
        "is_locked": False,
        "switch_state": None,
        "is_open": False,
        "metadata": itm.get("metadata_json") or {},
    }


def _scene_object_items(
    ent: WorldEntity, override: dict[str, Any], scene_names: dict[str, str]
) -> list[dict[str, Any]]:
    """A scene object plus the items stored inside it (containers)."""
    loc_id = _entity_scene_id(ent, override)
    loc_name = scene_names.get(loc_id, loc_id)
    is_hidden = bool(override.get("is_hidden", getattr(ent, "is_hidden", False)))
    is_portable = getattr(ent, "is_portable", None)
    items = [
        {
            "id": ent.id,
            "name": ent.name,
            "description": ent.description or "",
            "item_type": ent.item_type or ent.entity_type or "OBJECT",
            "slot": getattr(ent, "slot", None),
            "image_url": ent.image_url,
            "location_type": "scene",
            "location_id": loc_id,
            "location_name": loc_name,
            "is_hidden": is_hidden,
            "is_portable": is_portable if is_portable is not None else True,
            "is_locked": bool(override.get("is_locked", getattr(ent, "is_locked", False))),
            "switch_state": override.get("switch_state", getattr(ent, "switch_state", None)),
            "is_open": bool(override.get("is_open", getattr(ent, "is_open", False))),
            "metadata": ent.metadata_json or {},
        }
    ]
    contents = override.get("inventory", getattr(ent, "inventory", None) or [])
    if isinstance(contents, list):
        items.extend(
            _carried_item(itm, "container", ent.id, f"{ent.name} (in {loc_name})", is_hidden)
            for itm in contents
            if isinstance(itm, dict)
        )
    return items


def _build_items_matrix(
    avatar: Avatar | None,
    objects: list[WorldEntity],
    npcs_data: list[dict[str, Any]],
    entity_overrides: dict[str, Any],
    scene_names: dict[str, str],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if avatar and avatar.inventory:
        hero = f"Hero ({avatar.name})"
        items.extend(
            _carried_item(itm, "avatar", avatar.id, hero, False)
            for itm in avatar.inventory
            if isinstance(itm, dict)
        )
    for ent in objects:
        items.extend(_scene_object_items(ent, entity_overrides.get(ent.id, {}), scene_names))
    for npc in npcs_data:
        location = f"{npc['name']} (in {npc['current_scene_name']})"
        items.extend(
            _carried_item(itm, "npc", npc["id"], location, npc["is_hidden"])
            for itm in npc["inventory"]
            if isinstance(itm, dict)
        )
    return items


def _build_exits_data(
    exit_lookup: dict[str, WorldExit], exit_overrides: dict[str, Any]
) -> list[dict[str, Any]]:
    exits = []
    for ex in exit_lookup.values():
        override = exit_overrides.get(ex.id, {})
        exits.append(
            {
                "id": ex.id,
                "from_scene_id": ex.from_scene_id,
                "to_scene_id": ex.to_scene_id,
                "label": ex.label or "Passage",
                "is_locked": bool(override.get("is_locked", ex.is_locked)),
                "is_secret": bool(override.get("is_secret", getattr(ex, "is_secret", False))),
                "lock_description": ex.lock_description,
            }
        )
    return exits


def _avatar_section(avatar: Avatar | None) -> dict[str, Any]:
    if not avatar:
        return {
            "id": None,
            "name": "Protagonist",
            "hp": 100,
            "max_hp": 100,
            "stamina": 50,
            "max_stamina": 50,
            "mana": 50,
            "max_mana": 50,
            "exp": 0,
            "stats": dict.fromkeys(_STAT_FIELDS, 10),
        }
    return {
        "id": avatar.id,
        "name": avatar.name,
        "hp": avatar.hp,
        "max_hp": avatar.max_hp,
        "stamina": avatar.stamina,
        "max_stamina": avatar.max_stamina,
        "mana": avatar.mana,
        "max_mana": avatar.max_mana,
        "exp": avatar.exp,
        "stats": {stat: getattr(avatar, stat, 10) for stat in _STAT_FIELDS},
    }


def _session_section(
    state: SessionState, adventure: AdventureTemplate | None, scene_names: dict[str, str]
) -> dict[str, Any]:
    session = state.session
    fallback_title = session.adventure_title if session else "Adventure"
    title = adventure.title if adventure else fallback_title
    return {
        "id": state.session_id,
        "template_id": state.template_id,
        "adventure_title": title,
        "current_scene_id": state.current_scene_id,
        "current_scene_name": scene_names.get(state.current_scene_id, state.current_scene_id),
        "in_game_time": state.in_game_time,
        "time_system": state.time_system,
        "is_debug_enabled": state.is_debug_enabled,
        "status": session.status if session else "active",
        "status_note": session.status_note if session else None,
    }


def _runtime_sections(state: SessionState, avatar: Avatar | None) -> dict[str, Any]:
    return {
        "runtime": {
            "current_scene_id": state.current_scene_id,
            "in_game_time": state.in_game_time,
            "is_debug_enabled": state.is_debug_enabled,
            "entity_overrides": state.entity_states or {},
            "exit_overrides": state.exit_states or {},
            "quests": state.quests or [],
            "world_memories": state.world_memories or [],
        },
        "raw": {
            "session_id": state.session_id,
            "template_id": state.template_id,
            "current_scene_id": state.current_scene_id,
            "in_game_time": state.in_game_time,
            "is_debug_enabled": state.is_debug_enabled,
            "entity_states": state.entity_states or {},
            "exit_states": state.exit_states or {},
            "quests": state.quests or [],
            "world_memories": state.world_memories or [],
            "avatar_stats": {
                "hp": avatar.hp if avatar else None,
                "mana": avatar.mana if avatar else None,
                "stamina": avatar.stamina if avatar else None,
                "exp": avatar.exp if avatar else None,
            },
        },
    }


async def _load_blueprint(db: AsyncSession, template_id: str) -> dict[str, Any] | None:
    try:
        from backend.api.routes.adventures.editor import _build_adventure_editor_assets

        blueprint_obj = await _build_adventure_editor_assets(template_id, db)
        return blueprint_obj.model_dump()
    except Exception as exc:
        logger.warning("Could not build blueprint assets for debug: %s", exc)
        return None


async def _load_world(db: AsyncSession, state: SessionState):
    scenes = (
        (
            await db.execute(
                select(WorldScene)
                .where(_session_or_template(WorldScene, state))
                .order_by(WorldScene.id)
            )
        )
        .scalars()
        .all()
    )
    exits = (
        (await db.execute(select(WorldExit).where(_session_or_template(WorldExit, state))))
        .scalars()
        .all()
    )
    entities = (
        (
            await db.execute(
                select(WorldEntity)
                .where(_session_or_template(WorldEntity, state))
                .order_by(WorldEntity.id)
            )
        )
        .scalars()
        .all()
    )
    session_id = state.session_id
    return (
        _prefer_session_rows(list(scenes), lambda s: s.id, session_id),
        _prefer_session_rows(
            list(exits), lambda ex: f"{ex.from_scene_id}->{ex.to_scene_id}", session_id
        ),
        _prefer_session_rows(list(entities), lambda ent: ent.id, session_id),
    )


async def build_session_debug_payload(
    db: AsyncSession,
    state: SessionState,
    adventure: AdventureTemplate | None,
    avatar: Avatar | None,
) -> dict[str, Any]:
    """Assembles unified debug data including all NPCs with stats/locations, full map with NPC indicators, and complete items matrix."""
    scene_lookup, exit_lookup, entity_lookup = await _load_world(db, state)
    scene_names = {s.id: (s.label or s.id) for s in scene_lookup.values()}
    entity_overrides = state.entity_states or {}

    npcs_data = [
        _build_npc_info(ent, entity_overrides.get(ent.id, {}), scene_names, state.current_scene_id)
        for ent in entity_lookup.values()
        if ent.entity_type == "NPC"
    ]
    scene_npcs: dict[str, list[dict[str, Any]]] = {s_id: [] for s_id in scene_lookup}
    for npc in npcs_data:
        scene_npcs.setdefault(npc["current_scene_id"], []).append(_scene_npc_summary(npc))

    objects = [ent for ent in entity_lookup.values() if ent.entity_type != "NPC"]
    items_data = _build_items_matrix(avatar, objects, npcs_data, entity_overrides, scene_names)

    nodes_data = {
        s.id: {
            "id": s.id,
            "label": s.label or s.id,
            "description": s.description or "",
            "image_url": s.image_url,
            "is_current": s.id == state.current_scene_id,
            "npcs": scene_npcs.get(s.id, []),
        }
        for s in scene_lookup.values()
    }

    return {
        "session": _session_section(state, adventure, scene_names),
        "avatar": _avatar_section(avatar),
        "npcs": npcs_data,
        "scene_npcs": scene_npcs,
        "items": items_data,
        "map": {
            "nodes": nodes_data,
            "exits": _build_exits_data(exit_lookup, state.exit_states or {}),
            "current_scene_id": state.current_scene_id,
            "scene_npcs": scene_npcs,
        },
        "blueprint": await _load_blueprint(db, state.template_id),
        **_runtime_sections(state, avatar),
    }
