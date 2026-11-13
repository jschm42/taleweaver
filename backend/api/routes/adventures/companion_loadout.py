"""The companion's loadout from the hero dialog: equipment and ability switches.

* ``/companion_equip <item>[ | <slot>]``: equips an item the companion carries.
* ``/companion_unequip <slot>``: empties a slot; the item stays carried.
* ``/companion_ability <ability id> on|off``: whether the companion uses one of its special
  actions (defined on the NPC in the editor) in combat.

Equipping needs the companion in the protagonist's scene, like handovers; switching abilities
works anywhere. None of these runs a Game Master turn.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.companion_inventory import reachable_companion
from backend.api.routes.adventures.companion_sheet import held_entries, held_items
from backend.engine.party.equipment import (
    choose_slot,
    equip_item,
    is_equippable,
    normalize_slot,
    read_equipment,
    unequip_slot,
)
from backend.engine.party.follow import session_npc
from backend.engine.party.party_state import read_party, store_party

EQUIP_USAGE = "Usage: /companion_equip <item>[ | <slot>]"
UNEQUIP_USAGE = "Usage: /companion_unequip <slot>"
ABILITY_USAGE = "Usage: /companion_ability <ability id> on|off"

Events = list[tuple[str, str]]


async def _say(manager: Any, text: str) -> Events:
    await manager._save_chat_message("system", text)
    return [("system", text)]


def _store_states(manager: Any, entity_states: dict[str, Any]) -> None:
    manager.state.entity_states = entity_states
    flag_modified(manager.state, "entity_states")


def _match(items: list[dict[str, Any]], wanted: str) -> dict[str, Any] | None:
    low = wanted.strip().lower()
    return next(
        (i for i in items if low in (str(i.get("id", "")).lower(), str(i.get("name", "")).lower())),
        None,
    )


async def equip_companion(manager: Any, args: str) -> Events:
    item_ref, _, slot_ref = (args or "").partition("|")
    if not item_ref.strip():
        return [("system", EQUIP_USAGE)]
    row, refusal = await reachable_companion(manager)
    if row is None:
        return [("system", refusal or "You have no companion.")]
    states = dict(manager.state.entity_states or {})
    items = await held_items(manager.db, manager.state.session_id, held_entries(states, row), {})
    item = _match(items, item_ref)
    if item is None:
        return [("system", f"{row.name} doesn't carry {item_ref.strip()}.")]
    if not is_equippable(item):
        return [("system", f"{item['name']} cannot be equipped.")]
    slot = choose_slot(item, slot_ref.strip(), read_equipment(states, row.id))
    if not slot:
        return [("system", f"Unknown slot '{slot_ref.strip()}'.")]
    equip_item(states, row.id, str(item["id"]), slot)
    _store_states(manager, states)
    return await _say(manager, f"{row.name} equips {item['name']} ({slot}).")


async def unequip_companion(manager: Any, args: str) -> Events:
    slot = normalize_slot(args)
    if not slot:
        return [("system", UNEQUIP_USAGE)]
    row, refusal = await reachable_companion(manager)
    if row is None:
        return [("system", refusal or "You have no companion.")]
    states = dict(manager.state.entity_states or {})
    item_id = unequip_slot(states, row.id, slot)
    if not item_id:
        return [("system", f"{row.name} has nothing equipped in {slot}.")]
    _store_states(manager, states)
    return await _say(manager, f"{row.name} takes off {item_id} ({slot}).")


async def toggle_companion_ability(manager: Any, args: str) -> Events:
    parts = (args or "").split()
    if len(parts) != 2 or parts[1].lower() not in ("on", "off"):
        return [("system", ABILITY_USAGE)]
    party = read_party(manager.state.entity_states)
    row = None
    if party.active_id:
        row = await session_npc(manager.db, manager.state.session_id, party.active_id)
    if row is None:
        return [("system", "You have no companion.")]
    meta = row.metadata_json if isinstance(row.metadata_json, dict) else {}
    known = {str(a.get("id")): a for a in meta.get("special_actions") or [] if isinstance(a, dict)}
    ability = known.get(parts[0])
    if ability is None:
        return [("system", f"{row.name} has no ability '{parts[0]}'.")]
    enabled = parts[1].lower() == "on"
    party.set_ability(row.id, parts[0], enabled)
    states = dict(manager.state.entity_states or {})
    store_party(states, party)
    _store_states(manager, states)
    name = ability.get("name") or parts[0]
    verb = "uses" if enabled else "no longer uses"
    return await _say(manager, f"{row.name} {verb} {name} in combat.")
