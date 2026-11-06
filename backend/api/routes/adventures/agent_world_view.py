"""What the play-agent sees of the current room, and name lookups for its commands.

The view is built from `AdventureLogic.build_session_entities`, the same payload the Room
Discoveries panel renders for a human player, so the agent gets no hidden information:
hidden entities, lock codes and key items stay out. Container contents are only listed
once the agent opened that container with `/open` (a human sees them in the open modal).
"""

from __future__ import annotations

from typing import Any

from backend.api.routes.adventures.logic import AdventureLogic
from backend.engine.interaction.switch_states import state_label

OPENED_CONTAINERS_KEY = "opened_containers"
CONTAINER_TYPES = {"CONTAINER", "CONTAINER_SWITCH"}
SWITCH_TYPES = {"SWITCH", "CONTAINER_SWITCH"}


def norm(value: Any) -> str:
    return " ".join(str(value or "").lower().split())


def lock_hint(label: str, code: Any, item: Any) -> str:
    """How the agent can open a locked exit or container (never the secret itself)."""
    if code:
        return f"Requires a code -> `/unlock {label} code <code>`"
    if item:
        return f"Requires a key item -> `/unlock {label} with <item name>`"
    return "Opens through the story: find the right action or item (e.g. `/use <item> on <target>`)"


async def load_room_entities(db: Any, state: Any) -> list[dict[str, Any]]:
    """Player-visible entities of the current scene (NPCs and objects)."""
    return await AdventureLogic.build_session_entities(db, state)


def item_type(entity: dict[str, Any]) -> str:
    return str(entity.get("item_type") or "").upper()


def is_npc(entity: dict[str, Any]) -> bool:
    return str(entity.get("entity_type") or "").upper() == "NPC"


def switch_config(entity: dict[str, Any]) -> dict[str, Any]:
    meta = entity.get("metadata_json") if isinstance(entity.get("metadata_json"), dict) else {}
    config = meta.get("switch")
    return config if isinstance(config, dict) else {}


def is_switch(entity: dict[str, Any]) -> bool:
    return item_type(entity) in SWITCH_TYPES or bool(switch_config(entity))


def is_container(entity: dict[str, Any]) -> bool:
    return item_type(entity) in CONTAINER_TYPES


def find_entity(
    entities: list[dict[str, Any]], ref: str, kind: Any = None
) -> dict[str, Any] | None:
    """Exact name/ID match first, then a partial name match (e.g. "chest" for "Old Chest")."""
    wanted = norm(ref).strip("\"'")
    if not wanted:
        return None
    candidates = [e for e in entities if kind is None or kind(e)]
    exact = next(
        (e for e in candidates if wanted in (norm(e.get("name")), norm(e.get("id")))), None
    )
    if exact:
        return exact
    return next((e for e in candidates if wanted in norm(e.get("name"))), None)


def switch_states(entity: dict[str, Any]) -> tuple[str, list[str], set[str]]:
    """(current state, all states, disabled states) of a switch, as upper-case IDs."""
    config = switch_config(entity)
    states = [str(s).strip().upper() for s in config.get("states") or [] if str(s).strip()]
    initial = str(config.get("initial_state") or (states[0] if states else "")).strip().upper()
    current = str(entity.get("switch_state") or initial).strip().upper()
    raw_disabled = entity.get("disabled_switch_states") or config.get("disabled_states") or []
    disabled = {str(s).strip().upper() for s in raw_disabled if str(s).strip()}
    return current, states, disabled


def _switch_line(entity: dict[str, Any]) -> str:
    config = switch_config(entity)
    current, states, disabled = switch_states(entity)
    options = [
        f"{s} ({state_label(config, s)})" if state_label(config, s) != s else s
        for s in states
        if s != current and s not in disabled
    ]
    target = f"/switch {entity.get('name')} <STATE>"
    line = f"switch, currently {state_label(config, current)} [{current}]"
    if options:
        line += f"; can be set to: {', '.join(options)} -> `{target}`"
    status = str(entity.get("switch_status_text") or "").strip()
    return f"{line}; display: {status}" if status else line


def _container_line(entity: dict[str, Any], opened: set[str]) -> str:
    name = entity.get("name")
    meta = entity.get("metadata_json") if isinstance(entity.get("metadata_json"), dict) else {}
    if entity.get("locked"):
        return "container, LOCKED: " + lock_hint(
            name, meta.get("code_to_unlock"), meta.get("item_to_unlock")
        )
    if str(entity.get("id")) not in opened:
        return f"container, closed -> look inside with `/open {name}`"
    contents = [
        f"{i.get('name') or i.get('id')}{' (locked)' if i.get('locked') else ''}"
        for i in entity.get("inventory") or []
        if isinstance(i, dict) and not i.get("is_hidden")
    ]
    if not contents:
        return f"container, opened, empty -> store items with `/put <item> in {name}`"
    return (
        f"container, opened, contains: {', '.join(contents)} -> "
        f"`/take <item> from {name}`, `/container_take_all {name}`, `/put <item> in {name}`"
    )


def describe_object(entity: dict[str, Any], opened: set[str]) -> str:
    parts = []
    if is_container(entity):
        parts.append(_container_line(entity, opened))
    if is_switch(entity):
        parts.append(_switch_line(entity))
    if not parts and entity.get("locked"):
        parts.append("cannot be taken yet")
    suffix = f" ({'; '.join(parts)})" if parts else ""
    return f"{entity.get('name')}{suffix}"


def format_room_objects(entities: list[dict[str, Any]], opened: set[str]) -> str:
    """One line per visible object of the room, or "None"."""
    lines = [f"- {describe_object(e, opened)}" for e in entities if not is_npc(e) and e.get("name")]
    return "\n".join(lines) if lines else "None"


def opened_container_ids(agent_state: dict[str, Any]) -> set[str]:
    raw = agent_state.get(OPENED_CONTAINERS_KEY)
    return {str(i) for i in raw} if isinstance(raw, list) else set()
