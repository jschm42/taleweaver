"""Handing items between the protagonist and the active companion (hero dialog).

``/companion_give <item>[, <item> ...]`` moves carried items to the companion,
``/companion_take <item>[, <item> ...]`` takes items the companion carries. Both are plain
inventory management: no Game Master turn and no ``on_receive_item`` trigger (unlike
``/give_items``). The moves go through the scripting engine's ``ItemMover``, so every item
keeps exactly one holder, and are stored with the turn's changeset applier.

The companion has to stand in the protagonist's scene and must not be defeated. Quest items
(``metadata_json.quest_item``) cannot be handed to the companion.
"""

from __future__ import annotations

from typing import Any

from backend.api.routes.adventures.container_put import pick_items, split_item_refs
from backend.engine.party.follow import session_npc
from backend.engine.party.orders import companion_refusal
from backend.engine.party.party_state import read_party
from backend.engine.rules.quest_items import quest_item_ids, quest_item_refusal
from backend.engine.scripting.item_transfer import ref_id
from backend.models.world_entity import WorldEntity

GIVE = "give"
TAKE = "take"
USAGE = {
    GIVE: "Usage: /companion_give <item>[, <item> ...]",
    TAKE: "Usage: /companion_take <item>[, <item> ...]",
}

Events = list[tuple[str, str]]


async def reachable_companion(manager: Any) -> tuple[WorldEntity | None, str | None]:
    """(companion row, None) or (None, why the handover is not possible)."""
    party = read_party(manager.state.entity_states)
    row = None
    if party.active_id:
        row = await session_npc(manager.db, manager.state.session_id, party.active_id)
    if row is None:
        return None, "You have no companion."
    scene_id = str(manager.state.current_scene_id or "")
    refusal = companion_refusal(dict(manager.state.entity_states or {}), row, scene_id)
    return (None, refusal) if refusal else (row, None)


def _give(
    mover: Any, avatar: Any, npc_id: str, refs: list[str], quest_ids: set[str]
) -> tuple[list[str], list[str], list[str]]:
    """Moves the named carried items to the companion: (moved, missing, kept quest items)."""
    picked, missing = pick_items(list(avatar.inventory or []), refs, "")
    moved: list[str] = []
    kept: list[str] = []
    for entry in picked:
        if ref_id(entry) in quest_ids:
            kept.append(str(entry.get("name") if isinstance(entry, dict) else ref_id(entry)))
            continue
        item_id = mover.item_id(ref_id(entry))
        if item_id and mover.to_npc(item_id, npc_id):
            moved.append(str(entry.get("name") if isinstance(entry, dict) else item_id))
            continue
        missing.append(ref_id(entry))
    return moved, missing, kept


def _take(mover: Any, npc_id: str, refs: list[str]) -> tuple[list[str], list[str]]:
    held = {proxy.id.upper(): proxy for proxy in mover.contents(npc_id)}
    by_name = {str(proxy.name).strip().lower(): proxy for proxy in held.values()}
    moved: list[str] = []
    missing: list[str] = []
    for wanted in refs:
        proxy = held.get(wanted.strip().upper()) or by_name.get(wanted.strip().lower())
        if proxy is None or mover.to_player(proxy.id) is None:
            missing.append(wanted)
            continue
        held.pop(proxy.id.upper(), None)
        moved.append(str(proxy.name))
    return moved, missing


async def transfer_companion_items(manager: Any, direction: str, args: str) -> Events:
    """Runs ``/companion_give`` or ``/companion_take``; returns the chat lines to stream."""
    refs = split_item_refs(args or "")
    if not refs:
        return [("system", USAGE[direction])]
    row, refusal = await reachable_companion(manager)
    if row is None:
        return [("system", refusal or "You have no companion.")]
    context = await manager._build_script_context()
    mover = context.objects.mover
    kept: list[str] = []
    if direction == GIVE:
        carried = (ref_id(entry) for entry in manager.avatar.inventory or [])
        quest_ids = await quest_item_ids(manager.db, manager.state.session_id, carried)
        moved, missing, kept = _give(mover, manager.avatar, row.id, refs, quest_ids)
    else:
        moved, missing = _take(mover, row.id, refs)
    events: Events = []
    if kept:
        events.append(("system", quest_item_refusal(kept)))
    if moved:
        notices = await manager._apply_script_changeset(context.changeset)
        events.extend(("system", str(text)) for text in notices)
    if moved and direction == GIVE:
        text = f"{row.name} now carries: {', '.join(moved)}."
        await manager._save_chat_message("system", text)
        events.append(("system", text))
    if missing:
        holder = "You don't carry" if direction == GIVE else f"{row.name} doesn't carry"
        events.append(("system", f"{holder} {', '.join(missing)}."))
    return events
