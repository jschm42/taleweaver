"""Agent-only action layer: deterministic movement and unlocking for the play-agent.

Human players move and unlock through UI widgets (exit hotspots, code/item modals). The
play-agent can only type, so this module translates a small set of agent commands into
the same engine operations:

- `/go <exit or destination>`          -> `/traverse_exit <exit id>` (regular turn)
- `/unlock <target> with <item>`       -> exit/container unlock with a key item
- `/unlock <target> code <code>`       -> exit/container unlock with a code
- `/unlock <target>`                   -> exit/container unlock guarded by a script expression
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException
from sqlalchemy import and_, or_, select

from backend.api.routes.adventures.turn_context_helpers import orient_exits
from backend.models.avatar import Avatar
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene

GO_COMMANDS = ("/go", "/move", "/walk")
UNLOCK_COMMAND = "/unlock"

_ITEM_PATTERN = re.compile(r"^(?P<target>.+?)\s+(?:with|using)\s+(?P<value>.+)$", re.IGNORECASE)
_CODE_PATTERN = re.compile(
    r"^(?P<target>.+?)\s+(?:code|passcode|password|pin)\s*[:=]?\s*(?P<value>\S+)$",
    re.IGNORECASE,
)


@dataclass
class SceneExit:
    exit: WorldExit
    target_label: str


@dataclass
class AgentActionOutcome:
    """Either a command to play as a regular turn, or a message for an action handled here."""

    turn_command: str | None = None
    message: str | None = None


def _routes() -> Any:
    # Imported lazily: the gameplay routes module imports the turn engine, which
    # imports the agent modules.
    from backend.api.routes.adventures import gameplay

    return gameplay


def _norm(value: Any) -> str:
    return " ".join(str(value or "").lower().split())


async def load_scene_exits(db: Any, game_id: str, scene_id: str | None) -> list[SceneExit]:
    """Exits leading out of the current scene, oriented, with their destination labels."""
    if not scene_id:
        return []
    exit_res = await db.execute(
        select(WorldExit).where(
            WorldExit.session_id == game_id,
            or_(
                WorldExit.from_scene_id == scene_id,
                and_(
                    WorldExit.to_scene_id == scene_id,
                    WorldExit.exit_type == "bidirectional",
                ),
            ),
        )
    )
    scene_res = await db.execute(select(WorldScene).where(WorldScene.session_id == game_id))
    labels = {s.id.lower(): s.label or s.id for s in scene_res.scalars().all()}
    exits = orient_exits(list(exit_res.scalars().all()), scene_id)
    return [
        SceneExit(exit=e, target_label=labels.get(str(e.to_scene_id).lower(), e.to_scene_id))
        for e in exits
        if not getattr(e, "is_hidden", False)
    ]


def _lock_hint(label: str, code: Any, item: Any) -> str:
    if code:
        return f"Requires a code -> `/unlock {label} code <code>`"
    if item:
        return f"Requires a key item -> `/unlock {label} with <item name>`"
    return "Opens through the story: find the right action or item (e.g. `/use <item> on <target>`)"


def format_exits_for_agent(scene_exits: list[SceneExit]) -> str:
    """Player-visible exit list with the exact command to use each exit."""
    if not scene_exits:
        return "EXITS FROM HERE: No visible exits."
    lines = []
    for scene_exit in scene_exits:
        ex = scene_exit.exit
        label = ex.label or "Exit"
        route = f"- {label} -> leads to {scene_exit.target_label}"
        if not ex.is_locked:
            lines.append(f"{route} [OPEN] -> `/go {label}`")
            continue
        lock_desc = f": {ex.lock_description}" if ex.lock_description else ""
        hint = _lock_hint(label, ex.code_to_unlock, ex.item_to_unlock)
        lines.append(f"{route} [LOCKED{lock_desc}] {hint}")
    return "EXITS FROM HERE (moving to another location ONLY works with `/go`):\n" + "\n".join(
        lines
    )


def container_lock_hint(entity: WorldEntity, states: dict[str, Any]) -> str:
    """Short lock annotation for a visible container, or empty when it is open."""
    meta = entity.metadata_json or {}
    entry = states.get(entity.id) if isinstance(states, dict) else None
    locked = (entry or {}).get("locked", bool(meta.get("locked")))
    if not locked:
        return " (container, open it with `/open`)"
    return f" (container, LOCKED: {_lock_hint(entity.name, meta.get('code_to_unlock'), meta.get('item_to_unlock'))})"


def _match_exit(scene_exits: list[SceneExit], ref: str) -> SceneExit | None:
    wanted = _norm(ref)
    if not wanted:
        return None
    for scene_exit in scene_exits:
        names = {_norm(scene_exit.exit.label), _norm(scene_exit.target_label)}
        names.add(_norm(scene_exit.exit.id))
        if wanted in names:
            return scene_exit
    # Fall back to partial matches such as "door" for "the heavy oak door".
    return next(
        (
            s
            for s in scene_exits
            if wanted in _norm(s.exit.label) or wanted in _norm(s.target_label)
        ),
        None,
    )


async def _match_container(manager: Any, ref: str) -> WorldEntity | None:
    res = await manager.db.execute(
        select(WorldEntity).where(
            WorldEntity.session_id == manager.game_id, WorldEntity.entity_type == "OBJECT"
        )
    )
    states = manager.state.entity_states or {}
    scene_id = _norm(manager.state.current_scene_id)
    wanted = _norm(ref)
    candidates = [
        e
        for e in res.scalars().all()
        if str(e.item_type or "").upper() == "CONTAINER"
        and _norm((states.get(e.id) or {}).get("current_scene_id", e.current_scene_id)) == scene_id
    ]
    exact = next((e for e in candidates if _norm(e.name) == wanted), None)
    return exact or next((e for e in candidates if wanted and wanted in _norm(e.name)), None)


async def _inventory_item_id(manager: Any, item_name: str) -> str | None:
    res = await manager.db.execute(select(Avatar).where(Avatar.id == manager.state.avatar_id))
    avatar = res.scalars().first()
    wanted = _norm(item_name)
    items = [i for i in (avatar.inventory if avatar else []) or [] if isinstance(i, dict)]
    exact = next((i for i in items if _norm(i.get("name")) == wanted), None)
    match = exact or next((i for i in items if wanted and wanted in _norm(i.get("name"))), None)
    return str(match.get("id")) if match and match.get("id") else None


async def _go(manager: Any, ref: str) -> AgentActionOutcome:
    scene_exits = await load_scene_exits(
        manager.db, manager.game_id, manager.state.current_scene_id
    )
    scene_exit = _match_exit(scene_exits, ref)
    if not scene_exit:
        options = ", ".join(s.exit.label for s in scene_exits) or "none"
        return AgentActionOutcome(
            message=f"There is no exit called '{ref}'. Exits here: {options}."
        )
    ex = scene_exit.exit
    if ex.is_locked:
        reason = ex.lock_description or "The way is locked."
        hint = _lock_hint(ex.label, ex.code_to_unlock, ex.item_to_unlock)
        return AgentActionOutcome(message=f"{ex.label} is locked. {reason} {hint}")
    return AgentActionOutcome(turn_command=f"/traverse_exit {ex.id}")


def _parse_unlock_args(args: str) -> tuple[str, str | None, str | None]:
    """Splits `/unlock` arguments into (target, item name, code)."""
    code_match = _CODE_PATTERN.match(args)
    if code_match:
        return code_match["target"].strip(), None, code_match["value"].strip()
    item_match = _ITEM_PATTERN.match(args)
    if item_match:
        return item_match["target"].strip(), item_match["value"].strip(), None
    return args.strip(), None, None


async def _unlock_exit(
    manager: Any, world_exit: WorldExit, item_id: str | None, code: str | None
) -> str:
    game_id, user, db = manager.game_id, manager.user, manager.db
    gameplay_routes = _routes()
    # Oriented copies of bidirectional exits lack guard fields; use the stored row.
    world_exit = (
        await gameplay_routes._resolve_session_exit(db, manager.state, world_exit.id) or world_exit
    )
    label = world_exit.label or "The exit"
    if not world_exit.is_locked:
        return f"{label} is already open. Use `/go {label}`."
    if code:
        payload = gameplay_routes.ExitUnlockCodeRequest(code=code)
        await gameplay_routes.unlock_exit_with_code(
            game_id, world_exit.id, payload, db=db, current_user=user
        )
    elif item_id:
        payload = gameplay_routes.ExitUnlockItemRequest(item_id=item_id)
        await gameplay_routes.unlock_exit_with_item(
            game_id, world_exit.id, payload, db=db, current_user=user
        )
    elif world_exit.unlock_expression and not world_exit.rule_to_unlock:
        await gameplay_routes.unlock_exit(game_id, world_exit.id, db=db, current_user=user)
    else:
        return f"{label} cannot be unlocked like that. " + _lock_hint(
            label, world_exit.code_to_unlock, world_exit.item_to_unlock
        )
    return f"{label} is now unlocked. Use `/go {label}` to pass through."


async def _unlock_container(
    manager: Any, entity: WorldEntity, item_id: str | None, code: str | None
) -> str:
    game_id, user, db = manager.game_id, manager.user, manager.db
    gameplay_routes = _routes()
    meta = entity.metadata_json or {}
    if code:
        payload = gameplay_routes.ContainerUnlockCodeRequest(code=code)
        await gameplay_routes.unlock_container_with_code(
            game_id, entity.id, payload, db=db, current_user=user
        )
    elif item_id:
        payload = gameplay_routes.ContainerUnlockItemRequest(item_id=item_id)
        await gameplay_routes.unlock_container_with_item(
            game_id, entity.id, payload, db=db, current_user=user
        )
    elif meta.get("unlock_expression") and not meta.get("rule_to_unlock"):
        await gameplay_routes.unlock_container(game_id, entity.id, db=db, current_user=user)
    else:
        return f"{entity.name} cannot be unlocked like that. " + _lock_hint(
            entity.name, meta.get("code_to_unlock"), meta.get("item_to_unlock")
        )
    return f"{entity.name} is now unlocked. Use `/open {entity.name}` to look inside."


async def _unlock(manager: Any, args: str) -> AgentActionOutcome:
    target, item_name, code = _parse_unlock_args(args)
    item_id = None
    if item_name:
        item_id = await _inventory_item_id(manager, item_name)
        if not item_id:
            return AgentActionOutcome(message=f"You are not carrying '{item_name}'.")

    scene_exits = await load_scene_exits(
        manager.db, manager.game_id, manager.state.current_scene_id
    )
    scene_exit = _match_exit(scene_exits, target)
    container = None if scene_exit else await _match_container(manager, target)
    if not scene_exit and not container:
        return AgentActionOutcome(message=f"There is nothing called '{target}' to unlock here.")

    try:
        if scene_exit:
            msg = await _unlock_exit(manager, scene_exit.exit, item_id, code)
        else:
            msg = await _unlock_container(manager, container, item_id, code)
    except HTTPException as exc:
        msg = f"Unlocking {target} failed: {exc.detail}"
    return AgentActionOutcome(message=msg)


async def execute_agent_action(manager: Any, action: str) -> AgentActionOutcome:
    """Handles agent-only commands; everything else is played as a regular turn."""
    parts = (action or "").strip().split(None, 1)
    command = parts[0].lower() if parts else ""
    args = parts[1].strip() if len(parts) > 1 else ""
    if command in GO_COMMANDS:
        return await _go(manager, args)
    if command == UNLOCK_COMMAND:
        return await _unlock(manager, args)
    return AgentActionOutcome(turn_command=action)
