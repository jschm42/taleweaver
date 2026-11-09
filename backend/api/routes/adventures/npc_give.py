"""Giving items to NPCs: ``/give_items <npc> | <item>[, <item> ...]`` or typed ``give X to Y``.

The items leave the protagonist's inventory and go into the NPC's inventory, carried out of
sight like ``tw.npcs.give_item``. Afterwards the NPC's inline ``on_receive_item`` trigger runs
once for the whole batch, with the items in scope as ``received_items`` (list of dicts) and
``received_item_ids`` (list of IDs). The caller then chains a Game Master turn so the NPC
reacts in character (``GiveOutcome.reaction_prompt``).

A typed ``give <item> to <npc>`` only becomes this command when the NPC stands in the scene
and the player carries at least one of the named items; anything else ("give the guard a
nod") stays a normal Game Master turn.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.container_put import pick_items, split_item_refs
from backend.engine.scripting.dialog import pending_dialog
from backend.engine.scripting.item_ops import INVENTORY_SCENE_ID
from backend.engine.scripting.item_transfer import ref_id
from backend.models.world_entity import WorldEntity

GIVE_USAGE = "Usage: /give_items <npc> | <item>[, <item> ...]"
_GIVE_PREFIX = re.compile(r"^\s*(?:i\s+)?give\s+", re.I)
_TO_DELIMITER = re.compile(r"\s+to\s+", re.I)
_AND_SEPARATOR = re.compile(r"\s+and\s+", re.I)
_ARTICLE = re.compile(r"^(?:the|a|an|my|some)\s+", re.I)


@dataclass
class GiveOutcome:
    """Events to stream and, after a successful handover, the prompt for the NPC's reaction."""

    events: list[tuple[str, str]] = field(default_factory=list)
    reaction_prompt: Optional[str] = None


def _strip_article(text: str) -> str:
    return _ARTICLE.sub("", text.strip()).strip()


def _item_label(entry: Any) -> str:
    return str(entry.get("name") or ref_id(entry)) if isinstance(entry, dict) else str(entry)


def _parse_give_parts(user_msg: str) -> tuple[str, list[str]] | None:
    clean_msg = (user_msg or "").strip().rstrip(" .!")
    prefix_match = _GIVE_PREFIX.match(clean_msg)
    if not prefix_match:
        return None

    rest = clean_msg[prefix_match.end() :].strip()
    parts = _TO_DELIMITER.split(rest)
    if len(parts) < 2:
        return None

    npc_hint = _strip_article(parts[-1].strip())
    items_part = " to ".join(parts[:-1]).strip()
    items_commas = _AND_SEPARATOR.sub(",", items_part)
    refs = [_strip_article(ref) for ref in items_commas.split(",") if _strip_article(ref)]
    if not npc_hint or not refs:
        return None
    return npc_hint, refs


async def typed_give_command(manager: Any, user_msg: str) -> Optional[str]:
    """``/give_items`` command for a typed "give X to Y", or None if it is no real handover."""
    parsed = _parse_give_parts(user_msg)
    if not parsed:
        return None
    npc_hint, refs = parsed
    npc = await manager._find_scene_npc_by_hint(npc_hint)
    if npc is None:
        return None
    picked, _missing = pick_items(list(manager.avatar.inventory or []), refs, str(npc.id))
    if not picked:
        return None
    return f"/give_items {npc.id} | {', '.join(refs)}"


async def give_items_to_npc(manager: Any, args: str) -> GiveOutcome:
    """Hands inventory items to an NPC in the current scene and runs its receive trigger."""
    npc_hint, _, item_part = (part.strip() for part in args.partition("|"))
    refs = split_item_refs(item_part)
    if not npc_hint or not refs:
        return GiveOutcome([("system", GIVE_USAGE)])

    npc = await manager._find_scene_npc_by_hint(npc_hint)
    if npc is None:
        return GiveOutcome([("system", f"There is nobody called '{npc_hint}' here.")])
    if manager._is_npc_defeated(npc):
        return GiveOutcome([("system", f"{npc.name} cannot take anything anymore.")])

    picked, missing = pick_items(list(manager.avatar.inventory or []), refs, str(npc.id))
    if not picked:
        return GiveOutcome([("system", f"You don't carry {', '.join(missing)}.")])

    await _hand_over(manager, npc, picked)
    names = ", ".join(_item_label(e) for e in picked)
    events = [await _say(manager, "system", f"You give {names} to {npc.name}.")]
    if missing:
        events.append(await _say(manager, "system", f"You don't carry {', '.join(missing)}."))
    events.extend(await _run_receive_trigger(manager, npc, picked))
    if pending_dialog(manager.state.entity_states):
        # The receive script asked the player something; the answer drives the reaction.
        return GiveOutcome(events)
    return GiveOutcome(events, _reaction_prompt(npc, names))


def _reaction_prompt(npc: WorldEntity, names: str) -> str:
    return (
        f"[ITEM_GIVEN] The player just gave {names} to {npc.name} (ID {npc.id}). "
        f"The engine already moved the item(s) into {npc.name}'s inventory: do not add, remove "
        "or move them again. React as the Game Master: let "
        f"{npc.name} respond in character and apply any rules or consequences that now trigger."
    )


async def _hand_over(manager: Any, npc: WorldEntity, picked: list[Any]) -> None:
    picked_ids = {ref_id(e) for e in picked}
    manager.avatar.inventory = [
        e for e in (manager.avatar.inventory or []) if ref_id(e) not in picked_ids
    ]
    states = dict(manager.state.entity_states or {})
    npc_state = dict(states.get(npc.id) or {})
    held = npc_state.get("inventory")
    held = list(held) if isinstance(held, list) else list(npc.inventory or [])
    npc.inventory = [*held, *picked]
    npc_state["inventory"] = list(npc.inventory)
    states[npc.id] = npc_state
    for item_id in picked_ids:
        states[item_id] = await _carry_out_of_sight(manager, item_id, states.get(item_id))
    manager.state.entity_states = states
    flag_modified(manager.state, "entity_states")


async def _carry_out_of_sight(manager: Any, item_id: str, state: Any) -> dict[str, Any]:
    """The item's own row: held by an NPC, it lies in no scene and is hidden."""
    placement = {"current_scene_id": INVENTORY_SCENE_ID, "is_in_inventory": False}
    res = await manager.db.execute(
        select(WorldEntity).where(
            WorldEntity.session_id == manager.state.session_id,
            func.upper(WorldEntity.id) == item_id,
        )
    )
    entity = res.scalars().first()
    if entity is not None:
        entity.current_scene_id = INVENTORY_SCENE_ID
        entity.is_in_inventory = False
        entity.is_hidden = True
    return {**(state if isinstance(state, dict) else {}), **placement, "is_hidden": True}


async def _say(manager: Any, role: str, text: str) -> tuple[str, str]:
    await manager._save_chat_message(role, text)
    return role, text


async def _run_receive_trigger(
    manager: Any, npc: WorldEntity, picked: list[Any]
) -> list[tuple[str, str]]:
    meta = dict(npc.metadata_json or {})
    events: list[tuple[str, str]] = []
    code = str(meta.get("on_receive_item_script") or "").strip()
    if code:
        received = [dict(e) if isinstance(e, dict) else {"id": e, "name": e} for e in picked]
        scope = {
            "received_items": received,
            "received_item_ids": [str(e.get("id")) for e in received],
        }
        messages = await manager._execute_inline_script(
            code, "on_receive_item", str(npc.id), extra_scope=scope
        )
        events.extend((str(getattr(m, "role", "system")), str(m)) for m in messages)
    text = str(meta.get("on_receive_item_text") or "").strip()
    if text:
        events.append(await _say(manager, "system", text))
    return events
