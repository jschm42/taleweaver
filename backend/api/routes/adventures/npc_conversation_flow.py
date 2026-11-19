"""NPC conversations in the turn loop: conversation beats, overheard topics and gossip.

``plan_conversation_beat`` runs once per player message after the logic pass (interaction
triggers, ``on_logic_pass_done``, turn scripts) and before the narration context is built.
It decides deterministically whether present NPCs talk with each other this narration
(``engine/conversations/chatter.py``) and stores the direction as ``pending_beat``; Pass 2
takes it once (``conversation_reminder``). An authored topic counts as heard right here: its
``on_heard_*`` hooks, the ``on_conversation_heard`` scripts and a world memory follow.

``spread_session_gossip`` runs at every in-game turn boundary when the adventure enables
gossip (``engine/conversations/gossip.py``).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.turn_context_helpers import apply_entity_overrides
from backend.api.routes.adventures.turn_pass_flow import sse_role_message
from backend.engine.conversations.chatter import (
    LISTEN_ALONE_DIRECTION,
    Beat,
    BeatRequest,
    beat_direction,
    beat_due,
    can_chat,
    plan_beat,
)
from backend.engine.conversations.gossip import spread_gossip
from backend.engine.conversations.settings import conversation_settings
from backend.engine.conversations.state import (
    heard_topics,
    mark_heard,
    player_chatter_enabled,
    read_conversations,
    take_pending_beat,
    write_conversations,
)
from backend.engine.conversations.topics import ConversationTopic
from backend.engine.interaction.switch_service import SwitchService
from backend.engine.party.companion_config import companion_config
from backend.engine.party.party_state import read_party
from backend.engine.rules.world_memories import add_world_memory, make_world_memory
from backend.engine.scripting import ScriptMessage
from backend.engine.scripting.dialog import pending_dialog
from backend.models.world_entity import WorldEntity

logger = logging.getLogger(__name__)

HEARD_TRIGGER = "on_conversation_heard"
LISTEN_PLAYER_ACTION = (
    "I keep quiet for a moment and listen to what the people around me are saying."
)


async def _session_npcs(manager: Any) -> list[WorldEntity]:
    res = await manager.db.execute(
        select(WorldEntity).where(
            WorldEntity.session_id == manager.state.session_id,
            WorldEntity.entity_type == "NPC",
            WorldEntity.is_in_inventory.is_(False),
        )
    )
    rows = list(res.scalars().all())
    apply_entity_overrides(rows, manager.state.entity_states or {})
    return rows


def _quiet_companion_id(entity_states: Any, npcs: list[WorldEntity]) -> str:
    """The active companion when its banter level is QUIET (it never starts a talk)."""
    active = read_party(entity_states).active_id or ""
    row = next((n for n in npcs if str(n.id).upper() == active.upper()), None)
    config = companion_config(
        row.metadata_json if row and isinstance(row.metadata_json, dict) else {}
    )
    return active if config and config.banter == "QUIET" else ""


def _skip_reason(manager: Any) -> str:
    message = str(getattr(manager, "current_user_message", "") or "")
    if not message:
        return "prologue"
    if message.lower().startswith("/continue_story"):
        return "continuation"
    if pending_dialog(manager.state.entity_states):
        return "open choice"
    if manager._has_combat_phase():
        return "combat"
    return ""


class _BeatPlanner:
    """One message's beat decision with lazy guard evaluation."""

    def __init__(self, manager: Any) -> None:
        self.manager = manager
        self._ctx: Any = None

    async def prepare_guards(self) -> None:
        self._ctx = await self.manager._build_script_context()

    def guard(self, expression: str) -> bool:
        if self._ctx is None:
            return False
        passed, _detail = SwitchService.evaluate_gate_expression(expression, self._ctx)
        return bool(passed)


def _request(manager: Any, data: dict[str, Any], addressed: bool, arrival: bool) -> BeatRequest:
    settings = conversation_settings(manager.adventure)
    return BeatRequest(
        level=settings.chatter,
        player_enabled=player_chatter_enabled(manager.state.entity_states),
        listen=bool(getattr(manager, "listen_requested", False)),
        arrival=arrival,
        addressed_npc=addressed,
        quiet=int(data.get("quiet") or 0),
    )


async def _plan(manager: Any, speakers: list[WorldEntity], data: dict[str, Any]) -> Beat | None:
    planner = _BeatPlanner(manager)
    await planner.prepare_guards()
    return plan_beat(
        speakers,
        manager.state.entity_states,
        heard_topics(manager.state.entity_states),
        planner.guard,
        data.get("last_pair") or [],
    )


def _store(manager: Any, data: dict[str, Any]) -> None:
    manager.state.entity_states = write_conversations(manager.state.entity_states or {}, data)
    flag_modified(manager.state, "entity_states")


async def plan_conversation_beat(
    manager: Any, interacted_ids: list[str]
) -> AsyncGenerator[str, None]:
    """Decides this message's conversation beat; yields the messages of topic hooks."""
    data = read_conversations(manager.state.entity_states)
    scene_id = str(manager.state.current_scene_id or "")
    arrival = data.get("scene") != scene_id
    if arrival:
        data.update({"scene": scene_id, "quiet": 0})
    skip = _skip_reason(manager)
    if skip:
        _store(manager, data)
        return
    npcs = await _session_npcs(manager)
    in_scene = [n for n in npcs if str(n.current_scene_id or "") == scene_id]
    quiet_companion = _quiet_companion_id(manager.state.entity_states, npcs)
    speakers = [n for n in in_scene if can_chat(n, quiet_companion)]
    scene_npc_ids = {str(n.id).upper() for n in in_scene}
    addressed = any(str(i).upper() in scene_npc_ids for i in interacted_ids or [])
    request = _request(manager, data, addressed, arrival)
    beat = await _plan(manager, speakers, data) if beat_due(request) else None
    if beat is None:
        _record_without_beat(data, request)
        _store(manager, data)
        return
    data.update(
        {
            "pending_beat": beat_direction(beat, listen=request.listen),
            "quiet": 0,
            "last_pair": sorted([str(beat.speaker_a.id).upper(), str(beat.speaker_b.id).upper()]),
        }
    )
    if beat.topic:
        mark_heard(data, beat.topic.id)
    _store(manager, data)
    if beat.topic:
        async for event in _topic_heard(manager, beat.topic):
            yield event


def _record_without_beat(data: dict[str, Any], request: BeatRequest) -> None:
    if request.listen:
        data["pending_beat"] = LISTEN_ALONE_DIRECTION
        return
    if not request.addressed_npc and not request.arrival:
        data["quiet"] = int(data.get("quiet") or 0) + 1


def _remember_topic(manager: Any, topic: ConversationTopic) -> None:
    text = topic.must_convey or topic.topic
    entry = make_world_memory(
        f"Overheard: {text}", scope="global", scene_id=manager.state.current_scene_id
    )
    memories, added = add_world_memory(list(manager.state.world_memories or []), entry)
    if added:
        manager.state.world_memories = memories
        flag_modified(manager.state, "world_memories")


async def _topic_heard(manager: Any, topic: ConversationTopic) -> AsyncGenerator[str, None]:
    """Consequences of an overheard topic: world memory, inline hooks, trigger scripts."""
    logger.info("[Turn %s] Conversation topic heard: %s", manager.game_id, topic.id)
    _remember_topic(manager, topic)
    messages: list[Any] = []
    if topic.on_heard_script:
        messages.extend(
            await manager._execute_inline_script(
                topic.on_heard_script, HEARD_TRIGGER, topic.owner_id
            )
        )
    if topic.on_heard_text:
        await manager._save_chat_message("system", topic.on_heard_text)
        messages.append(ScriptMessage(topic.on_heard_text, role="system"))
    runner = manager._get_script_runner()
    if runner.scripts:
        context = await manager._build_script_context()
        changeset = runner.run_trigger(HEARD_TRIGGER, context, target_id=topic.id)
        messages.extend(await manager._apply_script_changeset(changeset, None))
    for message in messages:
        yield sse_role_message(message)


def conversation_reminder(state: Any) -> str:
    """The conversation direction of this narration (taken once); empty without one."""
    return take_pending_beat(state)


async def spread_session_gossip(manager: Any) -> None:
    """Gossip at an in-game turn boundary (adventure switch ``gossip``)."""
    if not conversation_settings(manager.adventure).gossip:
        return
    states = manager.state.entity_states or {}
    updated, events = spread_gossip(states, await _session_npcs(manager))
    if not events:
        return
    for event in events:
        logger.info(
            "[Turn %s] Gossip: %s told %s about '%s'",
            manager.game_id,
            event.teller_id,
            event.listener_id,
            event.key,
        )
    manager.state.entity_states = updated
    flag_modified(manager.state, "entity_states")
