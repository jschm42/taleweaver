"""``/recruit <npc> [| <item>]``: the player recruits a companion NPC (context menu *Recruit*).

The NPC's ``companion.recruit_mode`` decides how (``engine/party/companion_config.py``):

* ``INSTANT``: the NPC joins at once.
* ``ITEM``: the *Recruit* dialog asks for an item; only ``recruit_item_id`` convinces the NPC.
  The NPC keeps that item (it moves into its inventory, quest items too). Any other item, or
  none, is a failure and the item stays with the player.
* ``SCRIPT`` (default): only scripts recruit it (``tw.party.recruit``); the command refuses.

Success runs the NPC's ``on_recruit_success_script`` / ``_text``, failure its
``on_recruit_failure_script`` / ``_text`` (``offered_item_id`` is in scope of both). Without a
success hook the caller chains a Game Master turn so the NPC greets the party in character.

A former party member (replaced by another companion, or dismissed after it accepted its item)
rejoins for free: no item, no hooks, a short GM reaction (``engine/party/recruit_state.py``).
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.container_put import pick_items
from backend.api.routes.adventures.npc_give import GiveOutcome
from backend.engine.party.companion_config import (
    RECRUIT_ITEM,
    CompanionConfig,
    companion_config,
)
from backend.engine.party.recruit_state import (
    is_active_companion,
    is_returning,
    mark_recruit_paid,
)
from backend.engine.scripting.item_transfer import ref_id
from backend.models.world_entity import WorldEntity

RECRUIT_USAGE = "Usage: /recruit <npc> [| <item>]"
SUCCESS_HOOK = "on_recruit_success"
FAILURE_HOOK = "on_recruit_failure"

Events = list[tuple[str, str]]


def _refusal(
    manager: Any, npc: WorldEntity, config: Optional[CompanionConfig], returning: bool
) -> str:
    """Why this NPC cannot be recruited with the Recruit action, or '' if it can."""
    if config is None or not config.recruitable:
        return f"{npc.name} does not want to join you."
    if is_active_companion(manager.state.entity_states, str(npc.id)):
        return f"{npc.name} already travels with you."
    if not (config.player_recruitable or returning):
        return f"{npc.name} does not want to join you."
    if manager._is_npc_defeated(npc):
        return f"{npc.name} cannot join you anymore."
    return ""


def _offered_entry(manager: Any, item_ref: str, npc_id: str) -> Optional[Any]:
    if not item_ref:
        return None
    picked, _missing = pick_items(list(manager.avatar.inventory or []), [item_ref], npc_id)
    return picked[0] if picked else None


async def recruit_companion_command(manager: Any, args: str) -> GiveOutcome:
    """Runs ``/recruit``; returns the events and, after a plain success, the reaction prompt."""
    npc_hint, _, item_ref = (part.strip() for part in (args or "").partition("|"))
    if not npc_hint:
        return GiveOutcome([("system", RECRUIT_USAGE)])
    npc = await manager._find_scene_npc_by_hint(npc_hint)
    if npc is None:
        return GiveOutcome([("system", f"There is nobody called '{npc_hint}' here.")])
    config = companion_config(npc.metadata_json)
    returning = is_returning(manager.state.entity_states, str(npc.id))
    refusal = _refusal(manager, npc, config, returning)
    if refusal:
        return GiveOutcome([("system", refusal)])
    if returning:
        return await _rejoin(manager, npc)

    offered = _offered_entry(manager, item_ref, str(npc.id))
    offered_id = ref_id(offered) if offered is not None else ""
    if config.recruit_mode == RECRUIT_ITEM and offered_id != config.recruit_item_id:
        return GiveOutcome(await _failure(manager, npc, offered_id or item_ref))
    return await _success(manager, npc, offered_id if config.recruit_mode == RECRUIT_ITEM else "")


async def _success(manager: Any, npc: WorldEntity, item_id: str) -> GiveOutcome:
    context = await manager._build_script_context()
    if item_id:
        context.objects.mover.to_npc(item_id, str(npc.id))
    context.party.recruit(str(npc.id))
    events: Events = [
        ("system", str(text)) for text in await manager._apply_script_changeset(context.changeset)
    ]
    if item_id:
        _remember_payment(manager, str(npc.id))
    events.append(await _say(manager, f"{npc.name} joins your party."))
    hook_events, has_hook = await _run_hook(manager, npc, SUCCESS_HOOK, item_id)
    events.extend(hook_events)
    return GiveOutcome(events, None if has_hook else _reaction_prompt(npc))


async def _rejoin(manager: Any, npc: WorldEntity) -> GiveOutcome:
    """A former party member comes back: no item, no recruit hooks."""
    context = await manager._build_script_context()
    context.party.recruit(str(npc.id))
    events: Events = [
        ("system", str(text)) for text in await manager._apply_script_changeset(context.changeset)
    ]
    events.append(await _say(manager, f"{npc.name} rejoins your party."))
    return GiveOutcome(events, _reaction_prompt(npc, rejoin=True))


def _remember_payment(manager: Any, npc_id: str) -> None:
    states = dict(manager.state.entity_states or {})
    mark_recruit_paid(states, npc_id)
    manager.state.entity_states = states
    flag_modified(manager.state, "entity_states")


async def _failure(manager: Any, npc: WorldEntity, item_id: str) -> Events:
    hook_events, has_hook = await _run_hook(manager, npc, FAILURE_HOOK, item_id)
    if has_hook:
        return hook_events
    return [await _say(manager, f"{npc.name} is not convinced and stays where they are.")]


async def _run_hook(manager: Any, npc: WorldEntity, hook: str, item_id: str) -> tuple[Events, bool]:
    """Runs ``<hook>_script`` and ``<hook>_text``: (events, whether the NPC has either)."""
    meta = dict(npc.metadata_json or {})
    code = str(meta.get(f"{hook}_script") or "").strip()
    text = str(meta.get(f"{hook}_text") or "").strip()
    events: Events = []
    if code:
        messages = await manager._execute_inline_script(
            code, hook, str(npc.id), extra_scope={"offered_item_id": item_id}
        )
        events.extend((str(getattr(m, "role", "system")), str(m)) for m in messages)
    if text:
        events.append(await _say(manager, text))
    return events, bool(code or text)


async def _say(manager: Any, text: str) -> tuple[str, str]:
    await manager._save_chat_message("system", text)
    return "system", text


def _reaction_prompt(npc: WorldEntity, rejoin: bool = False) -> str:
    joined = "came back to" if rejoin else "just agreed to join"
    return (
        f"[COMPANION_RECRUITED] {npc.name} (ID {npc.id}) {joined} the player's party. "
        "The engine already added them as the active companion: do not set companion_order and "
        f"do not move or remove items. Let {npc.name} accept briefly in character."
    )
