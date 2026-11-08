"""Agent commands for containers, item handovers and switches.

A human player does these through UI widgets (container modal, give dialog, switch panel).
The play-agent can only type, so its commands are resolved against the player-visible room
(`agent_world_view`) and rewritten into the exact engine commands those widgets send:

- `/open <container>`                    -> `/open <name>` (remembers the container was opened)
- `/take <item> from <container>`        -> `/container_take_item <container> | <item>`
- `/put <items> in <container>`          -> `/container_put_items <container> | <items>`
- `/give <items> to <npc>`               -> `/give_items <npc id> | <items>`
- `/switch <target> <state> [code]`      -> `/switch "<id>" <STATE> [code]`

The engine forms (`/container_take_item`, `/container_take_all`, `/container_put_items`,
`/container_drop_scene`, `/give_items`) are accepted too; their names are matched loosely.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.agent_world_view import (
    OPENED_CONTAINERS_KEY,
    find_entity,
    is_container,
    is_npc,
    is_switch,
    load_room_entities,
    norm,
    switch_config,
    switch_states,
)
from backend.engine.interaction.switch_states import state_label

_TAKE_FROM = re.compile(r"^(?P<items>.+?)\s+(?:from|out of)\s+(?P<target>.+)$", re.I)
_PUT_INTO = re.compile(r"^(?P<items>.+?)\s+(?:into|inside|in|onto|on)\s+(?P<target>.+)$", re.I)
_GIVE_TO = re.compile(r"^(?P<items>.+?)\s+to\s+(?P<target>.+)$", re.I)
_ITEM_SEPARATOR = re.compile(r"\s*,\s*|\s*\|\s*|\s+and\s+", re.I)
_ARTICLE = re.compile(r"^(?:the|a|an|my|some)\s+", re.I)


@dataclass
class AgentActionOutcome:
    """Either a command to play as a regular turn, or a message for an action handled here."""

    turn_command: str | None = None
    message: str | None = None


def _clean(text: str) -> str:
    return _ARTICLE.sub("", (text or "").strip().strip("\"'")).strip()


def _split_items(raw: str) -> list[str]:
    return [_clean(part) for part in _ITEM_SEPARATOR.split(raw or "") if _clean(part)]


def _names(entities: list[dict[str, Any]]) -> str:
    return ", ".join(str(e.get("name")) for e in entities if e.get("name")) or "none"


def _inventory(manager: Any) -> list[dict[str, Any]]:
    return [i for i in (manager.avatar.inventory or []) if isinstance(i, dict)]


def _exact_item_names(pool: list[dict[str, Any]], refs: list[str]) -> list[str]:
    """Maps loose item references ("key") to the exact names the engine matches."""
    resolved = []
    for ref in refs:
        match = find_entity(pool, ref)
        resolved.append(str(match.get("name") or match.get("id")) if match else ref)
    return resolved


def _remember_opened(manager: Any, container_id: str) -> None:
    agent_state = manager.state.entity_states.setdefault("__agent__", {})
    opened = list(agent_state.get(OPENED_CONTAINERS_KEY) or [])
    if container_id in opened:
        return
    agent_state[OPENED_CONTAINERS_KEY] = [*opened, container_id]
    flag_modified(manager.state, "entity_states")


async def _room(manager: Any) -> list[dict[str, Any]]:
    return await load_room_entities(manager.db, manager.state)


async def _container(manager: Any, ref: str) -> tuple[dict[str, Any] | None, str]:
    room = await _room(manager)
    container = find_entity(room, _clean(ref), is_container)
    if container:
        return container, ""
    options = _names([e for e in room if is_container(e)])
    return None, f"There is no container called '{ref}' here. Containers here: {options}."


async def _open(manager: Any, args: str) -> AgentActionOutcome | None:
    container, _ = await _container(manager, args)
    if not container:
        # Doors, books and mechanisms are opened through a regular Game Master turn.
        return None
    if not container.get("locked"):
        _remember_opened(manager, str(container["id"]))
    return AgentActionOutcome(turn_command=f"/open {container['name']}")


async def _take_from(manager: Any, container_ref: str, item_ref: str) -> AgentActionOutcome:
    container, error = await _container(manager, container_ref)
    if not container:
        return AgentActionOutcome(message=error)
    _remember_opened(manager, str(container["id"]))
    contents = [i for i in container.get("inventory") or [] if isinstance(i, dict)]
    item = _exact_item_names(contents, [_clean(item_ref)])[0]
    return AgentActionOutcome(turn_command=f"/container_take_item {container['name']} | {item}")


async def _take(manager: Any, args: str) -> AgentActionOutcome | None:
    match = _TAKE_FROM.match(args)
    if not match:
        return None
    room = await _room(manager)
    if not find_entity(room, _clean(match["target"]), is_container):
        # "take the coin from the guard" stays a Game Master turn.
        return None
    return await _take_from(manager, match["target"], match["items"])


async def _container_take_item(manager: Any, args: str) -> AgentActionOutcome:
    container_ref, _, item_ref = args.partition("|")
    return await _take_from(manager, container_ref, item_ref)


def _container_only(command: str) -> Callable[[Any, str], Awaitable[AgentActionOutcome]]:
    async def handler(manager: Any, args: str) -> AgentActionOutcome:
        container, error = await _container(manager, args)
        if not container:
            return AgentActionOutcome(message=error)
        _remember_opened(manager, str(container["id"]))
        return AgentActionOutcome(turn_command=f"{command} {container['name']}")

    return handler


async def _store(manager: Any, container_ref: str, items_raw: str) -> AgentActionOutcome:
    container, error = await _container(manager, container_ref)
    if not container:
        return AgentActionOutcome(message=error)
    items = _exact_item_names(_inventory(manager), _split_items(items_raw))
    if not items:
        return AgentActionOutcome(message=f"Name the items to put into {container['name']}.")
    return AgentActionOutcome(
        turn_command=f"/container_put_items {container['name']} | {', '.join(items)}"
    )


async def _put(manager: Any, args: str) -> AgentActionOutcome:
    match = _PUT_INTO.match(args)
    if not match:
        return AgentActionOutcome(message="Usage: /put <item>[, <item> ...] in <container>")
    return await _store(manager, match["target"], match["items"])


async def _container_put_items(manager: Any, args: str) -> AgentActionOutcome:
    container_ref, _, items_raw = args.partition("|")
    return await _store(manager, container_ref, items_raw)


async def _hand_over(manager: Any, npc_ref: str, items_raw: str) -> AgentActionOutcome:
    room = await _room(manager)
    npc = find_entity(room, _clean(npc_ref), is_npc)
    if not npc:
        options = _names([e for e in room if is_npc(e)])
        return AgentActionOutcome(
            message=f"There is nobody called '{npc_ref}' here. Characters here: {options}."
        )
    items = _exact_item_names(_inventory(manager), _split_items(items_raw))
    if not items:
        return AgentActionOutcome(message=f"Name the items to give to {npc['name']}.")
    return AgentActionOutcome(turn_command=f"/give_items {npc['id']} | {', '.join(items)}")


async def _give(manager: Any, args: str) -> AgentActionOutcome:
    match = _GIVE_TO.match(args)
    if not match:
        return AgentActionOutcome(message="Usage: /give <item>[, <item> ...] to <character>")
    return await _hand_over(manager, match["target"], match["items"])


async def _give_items(manager: Any, args: str) -> AgentActionOutcome:
    npc_ref, _, items_raw = args.partition("|")
    return await _hand_over(manager, npc_ref, items_raw)


def _split_switch_target(
    switches: list[dict[str, Any]], args: str
) -> tuple[dict[str, Any] | None, str]:
    """(switch, remaining text) for the longest switch name or ID the arguments start with."""
    text = norm(args.replace('"', " ").replace("'", " "))
    best: tuple[int, dict[str, Any]] | None = None
    for switch in switches:
        for token in (norm(switch.get("name")), norm(switch.get("id"))):
            fits = token and (text == token or text.startswith(token + " "))
            if fits and (best is None or len(token) > best[0]):
                best = (len(token), switch)
    if best is None:
        return None, ""
    return best[1], text[best[0] :].strip()


def _match_state(switch: dict[str, Any], rest: str) -> tuple[str | None, str]:
    """(state ID, code) from the text after the switch name; the state may be its label."""
    config = switch_config(switch)
    _, states, _ = switch_states(switch)
    by_name = {norm(s): s for s in states}
    by_name.update({norm(state_label(config, s)): s for s in states})
    if rest in by_name:
        return by_name[rest], ""
    for name in sorted(by_name, key=len, reverse=True):
        if rest.startswith(name + " "):
            return by_name[name], rest[len(name) :].strip()
    return None, ""


async def _switch(manager: Any, args: str) -> AgentActionOutcome:
    switches = [e for e in await _room(manager) if is_switch(e)]
    switch, rest = _split_switch_target(switches, args)
    if not switch:
        return AgentActionOutcome(
            message=f"There is no switch called '{args}' here. Switches here: {_names(switches)}."
        )
    state, code = _match_state(switch, rest)
    if not state:
        _, states, _ = switch_states(switch)
        return AgentActionOutcome(
            message=f"Unknown state '{rest}' for {switch['name']}. States: {', '.join(states)}."
        )
    suffix = f" {code}" if code else ""
    return AgentActionOutcome(turn_command=f'/switch "{switch["id"]}" {state}{suffix}')


_HANDLERS: dict[str, Callable[[Any, str], Awaitable[AgentActionOutcome | None]]] = {
    "/open": _open,
    "/take": _take,
    "/container_take_item": _container_take_item,
    "/container_take_all": _container_only("/container_take_all"),
    "/container_drop_scene": _container_only("/container_drop_scene"),
    "/put": _put,
    "/place": _put,
    "/store": _put,
    "/container_put_items": _container_put_items,
    "/give": _give,
    "/give_items": _give_items,
    "/switch": _switch,
    "/set": _switch,
}


async def execute_item_action(manager: Any, command: str, args: str) -> AgentActionOutcome | None:
    """Resolves an item/container/switch command, or None when it is not one of them."""
    handler = _HANDLERS.get(command)
    if handler is None or not args:
        return None
    return await handler(manager, args)
