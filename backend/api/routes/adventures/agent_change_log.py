"""System message listing what a play-agent turn changed in the world.

The agent plays fast and often through the Game Master, so a pickup or a flipped switch is
easy to miss in the narration. The turn stream takes a snapshot before the action and
compares it afterwards; every difference (items gained or lost, equipment, location,
switch states, locks, discoveries) ends up in one system message.

Values are read with fresh queries instead of the ORM objects of the turn, because those
may be expired after the turn's commits.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select

from backend.engine.interaction.switch_states import state_label
from backend.models.avatar import Avatar
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene

CHANGE_LOG_TITLE = "Play-Agent changes:"


@dataclass
class WorldSnapshot:
    avatar_id: str = ""
    scene_id: str | None = None
    carried: dict[str, str] = field(default_factory=dict)
    equipped: dict[str, str] = field(default_factory=dict)
    entities: dict[str, dict[str, Any]] = field(default_factory=dict)
    exits: dict[str, bool] = field(default_factory=dict)


def _item_key(item: Any) -> tuple[str, str] | None:
    if not isinstance(item, dict):
        return None
    name = str(item.get("name") or item.get("id") or "").strip()
    key = str(item.get("id") or name).strip().upper()
    return (key, name) if key else None


def _items(entries: Any) -> dict[str, str]:
    keyed = [_item_key(entry) for entry in entries or []]
    return dict(pair for pair in keyed if pair)


def _entity_view(entity: WorldEntity, override: dict[str, Any]) -> dict[str, Any]:
    meta = entity.metadata_json if isinstance(entity.metadata_json, dict) else {}
    switch = meta.get("switch") if isinstance(meta.get("switch"), dict) else {}
    return {
        "name": entity.name or entity.id,
        "switch": switch,
        "switch_state": override.get("switch_state") or switch.get("initial_state"),
        "locked": bool(override.get("locked", meta.get("locked", False))),
        "hidden": bool(override.get("is_hidden", entity.is_hidden)),
    }


async def take_snapshot(db: Any, game_id: str, avatar_id: str) -> WorldSnapshot:
    """Current carried items, location, switch/lock/visibility states and exit locks."""
    avatar_row = (
        await db.execute(select(Avatar.inventory, Avatar.equipment).where(Avatar.id == avatar_id))
    ).first()
    state_row = (
        await db.execute(
            select(SessionState.current_scene_id, SessionState.entity_states).where(
                SessionState.session_id == game_id
            )
        )
    ).first()
    overrides = (state_row.entity_states if state_row else None) or {}
    entities = (
        (await db.execute(select(WorldEntity).where(WorldEntity.session_id == game_id)))
        .scalars()
        .all()
    )
    exit_rows = (
        await db.execute(
            select(WorldExit.id, WorldExit.is_locked).where(WorldExit.session_id == game_id)
        )
    ).all()
    equipment = (
        avatar_row.equipment if avatar_row and isinstance(avatar_row.equipment, dict) else {}
    )
    return WorldSnapshot(
        avatar_id=avatar_id,
        scene_id=state_row.current_scene_id if state_row else None,
        carried=_items(avatar_row.inventory if avatar_row else []),
        equipped=_items(equipment.values()),
        entities={e.id: _entity_view(e, overrides.get(e.id) or {}) for e in entities},
        exits={row.id: bool(row.is_locked) for row in exit_rows},
    )


def _item_changes(before: WorldSnapshot, after: WorldSnapshot) -> list[str]:
    owned_before = {**before.carried, **before.equipped}
    owned_after = {**after.carried, **after.equipped}
    gained = [name for key, name in owned_after.items() if key not in owned_before]
    lost = [name for key, name in owned_before.items() if key not in owned_after]
    equipped = [name for key, name in after.equipped.items() if key not in before.equipped]
    lines = []
    if gained:
        lines.append(f"Received: {', '.join(gained)}")
    if lost:
        lines.append(f"No longer carried: {', '.join(lost)}")
    if equipped:
        lines.append(f"Equipped: {', '.join(equipped)}")
    return lines


def _entity_changes(before: WorldSnapshot, after: WorldSnapshot) -> list[str]:
    lines = []
    for entity_id, now in after.entities.items():
        old = before.entities.get(entity_id)
        if old is None:
            continue
        name = now["name"]
        if now["switch_state"] != old["switch_state"] and now["switch_state"]:
            old_label = state_label(old["switch"], old["switch_state"]) or "?"
            lines.append(
                f"{name}: {old_label} -> {state_label(now['switch'], now['switch_state'])}"
            )
        if now["locked"] != old["locked"]:
            lines.append(f"{'Locked' if now['locked'] else 'Unlocked'}: {name}")
        if old["hidden"] and not now["hidden"]:
            lines.append(f"Discovered: {name}")
    return lines


async def _exit_and_scene_changes(
    db: Any, game_id: str, before: WorldSnapshot, after: WorldSnapshot
) -> list[str]:
    opened = [eid for eid, locked in after.exits.items() if before.exits.get(eid) and not locked]
    moved = after.scene_id and after.scene_id != before.scene_id
    if not opened and not moved:
        return []
    scenes = {
        row.id: row.label or row.id
        for row in (
            await db.execute(
                select(WorldScene.id, WorldScene.label).where(WorldScene.session_id == game_id)
            )
        ).all()
    }
    lines = []
    if opened:
        exits = (
            await db.execute(
                select(WorldExit.label, WorldExit.to_scene_id).where(WorldExit.id.in_(opened))
            )
        ).all()
        names = [
            row.label or f"way to {scenes.get(row.to_scene_id, row.to_scene_id)}" for row in exits
        ]
        lines.append(f"Unlocked: {', '.join(names)}")
    if moved:
        lines.append(f"Moved to: {scenes.get(after.scene_id, after.scene_id)}")
    return lines


async def describe_changes(db: Any, game_id: str, before: WorldSnapshot) -> str:
    """The change log message for the turn, or an empty string when nothing changed."""
    after = await take_snapshot(db, game_id, before.avatar_id)
    lines = [
        *_item_changes(before, after),
        *_entity_changes(before, after),
        *await _exit_and_scene_changes(db, game_id, before, after),
    ]
    if not lines:
        return ""
    return CHANGE_LOG_TITLE + "\n" + "\n".join(f"- {line}" for line in lines)
