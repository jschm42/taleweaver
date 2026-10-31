"""``/container_put_items <container> | <item>[, <item> ...]``: the player stores items.

The items leave the protagonist's inventory and become the container's contents. Afterwards
the container's ``on_items_added`` trigger runs once for the whole batch, with the stored
items in scope as ``added_items`` (list of dicts) and ``added_item_ids`` (list of IDs).
"""

from __future__ import annotations

from typing import Any

from backend.engine.scripting.item_transfer import ref_id

PUT_USAGE = "Usage: /container_put_items <container> | <item>[, <item> ...]"
MAX_ITEMS_PER_PUT = 20


def _split_item_refs(raw: str) -> list[str]:
    refs = [part.strip() for part in raw.replace("|", ",").split(",")]
    return [ref for ref in refs if ref][:MAX_ITEMS_PER_PUT]


def _matches(entry: Any, wanted: str) -> bool:
    if ref_id(entry) == wanted.upper():
        return True
    return (
        isinstance(entry, dict) and str(entry.get("name") or "").strip().lower() == wanted.lower()
    )


def _pick_items(
    inventory: list[Any], refs: list[str], container_id: str
) -> tuple[list[Any], list[str]]:
    """(entries to store, refs not found); the container itself can never go inside."""
    remaining = list(inventory)
    picked: list[Any] = []
    missing: list[str] = []
    for wanted in refs:
        entry = next((e for e in remaining if _matches(e, wanted)), None)
        if entry is None or ref_id(entry) == container_id.upper():
            missing.append(wanted)
            continue
        remaining.remove(entry)
        picked.append(entry)
    return picked, missing


async def put_items_into_container(handler: Any, args: str) -> list[tuple[str, str]]:
    """Stores inventory items in a scene container; returns (role, text) events to stream."""
    container_hint, _, item_part = (part.strip() for part in args.partition("|"))
    refs = _split_item_refs(item_part)
    if not container_hint or not refs:
        return [("system", PUT_USAGE)]

    container, inventory_container, _idx = await handler._resolve_container_target(container_hint)
    if container is None:
        reason = "Items can only be put into containers that stand in the scene."
        missing = f"No container named '{container_hint}' was found."
        return [("system", reason if inventory_container else missing)]
    if handler._is_container_locked(container, None):
        return [("system", f"{container.name} is locked.")]

    picked, missing = _pick_items(list(handler.avatar.inventory or []), refs, str(container.id))
    if not picked:
        return [("system", f"You don't carry {', '.join(missing)}.")]

    await _store(handler, container, picked)
    names = ", ".join(str(e.get("name") or ref_id(e)) if isinstance(e, dict) else e for e in picked)
    events = [await _say(handler, "system", f"You put {names} into {container.name}.")]
    if missing:
        events.append(await _say(handler, "system", f"You don't carry {', '.join(missing)}."))
    return [*events, *await _run_trigger(handler, container, picked)]


async def _store(handler: Any, container: Any, picked: list[Any]) -> None:
    picked_ids = {ref_id(e) for e in picked}
    handler.avatar.inventory = [
        e for e in (handler.avatar.inventory or []) if ref_id(e) not in picked_ids
    ]
    contents = await handler._get_container_inventory(container, None)
    await handler._set_container_inventory(container, None, None, [*contents, *picked])
    for entry in picked:
        # The item now lies in the container's scene; the container listing hides it there.
        moved = entry if isinstance(entry, dict) else {"id": entry}
        await handler._move_container_item_to_scene(moved)


async def _say(handler: Any, role: str, text: str) -> tuple[str, str]:
    await handler._save_chat_message(role, text)
    return role, text


async def _run_trigger(handler: Any, container: Any, picked: list[Any]) -> list[tuple[str, str]]:
    meta = dict(container.metadata_json or {})
    events: list[tuple[str, str]] = []
    code = str(meta.get("on_items_added_script") or "").strip()
    if code:
        added = [dict(e) if isinstance(e, dict) else {"id": e, "name": e} for e in picked]
        scope = {"added_items": added, "added_item_ids": [str(e.get("id")) for e in added]}
        messages = await handler.manager._execute_inline_script(
            code, "on_items_added", str(container.id), extra_scope=scope
        )
        events.extend((str(getattr(m, "role", "system")), str(m)) for m in messages)
    text = str(meta.get("on_items_added_text") or "").strip()
    if text:
        events.append(await _say(handler, "system", text))
    return events
